import inspect

from distutils.version import LooseVersion
from typing import Any, Dict

import numpy as np
import pytest
import tensorflow as tf

from tensorflow.keras import Model

from scikeras.wrappers import BaseWrapper, KerasClassifier, KerasRegressor

from .mlp_models import dynamic_classifier, dynamic_regressor


@pytest.mark.parametrize(
    "wrapper, builder",
    [(KerasClassifier, dynamic_classifier), (KerasRegressor, dynamic_regressor),],
)
def test_routing_basic(wrapper, builder):
    n, d = 20, 3
    n_classes = 3
    X = np.random.uniform(size=(n, d)).astype(float)
    y = np.random.choice(n_classes, size=n).astype(int)

    foo_val = object()

    est = wrapper(model=builder, model__hidden_layer_sizes=(100,), model__foo=foo_val)

    def build_fn(hidden_layer_sizes, foo, compile_kwargs, params, meta):
        assert set(params.keys()) == set(est.get_params().keys())
        expected_meta = wrapper._meta - {
            "model_",
            "history_",
            "is_fitted_",
        }
        assert set(meta.keys()) == expected_meta
        assert set(compile_kwargs.keys()).issubset(wrapper._compile_kwargs)
        assert foo is foo_val
        return builder(
            hidden_layer_sizes=hidden_layer_sizes,
            compile_kwargs=compile_kwargs,
            meta=meta,
        )

    est = wrapper(model=build_fn, model__hidden_layer_sizes=(100,), model__foo=foo_val)
    est.fit(X, y)

    est = wrapper(model=build_fn, model__hidden_layer_sizes=(100,), foo=foo_val)
    est.fit(X, y)


@pytest.mark.parametrize(
    "wrapper, builder",
    [(KerasClassifier, dynamic_classifier), (KerasRegressor, dynamic_regressor),],
)
def test_routing_kwargs(wrapper, builder):
    """Tests that special parameters are passed if
    build_fn accepts kwargs.
    """
    n, d = 20, 3
    n_classes = 3
    X = np.random.uniform(size=(n, d)).astype(float)
    y = np.random.choice(n_classes, size=n).astype(int)

    def build_fn(*args, **kwargs):
        assert len(args) == 0, "No *args should be passed to `build_fn`"
        assert tuple(kwargs.keys()) == (
            "hidden_layer_sizes",
            "meta",
            "compile_kwargs",
            "params",
        ), "The number and order of **kwargs passed to `build_fn` should be fixed"
        meta = set(kwargs["meta"].keys())
        expected_meta = wrapper._meta - {
            "model_",
            "history_",
            "is_fitted_",
        }
        assert meta == expected_meta
        assert set(kwargs["compile_kwargs"].keys()).issubset(wrapper._compile_kwargs)
        kwargs.pop("params")  # dynamic_classifier/regressor don't accept it
        return builder(*args, **kwargs)

    est = wrapper(model=build_fn, model__hidden_layer_sizes=(100,))
    est.fit(X, y)


@pytest.mark.parametrize(
    "wrapper_class,build_fn",
    [(KerasClassifier, dynamic_classifier), (KerasRegressor, dynamic_regressor),],
)
def test_no_extra_meta(wrapper_class, build_fn):
    """Check that wrappers do not create any unexpected meta parameters.
    """
    n, d = 20, 3
    n_classes = 3
    X = np.random.uniform(size=(n, d)).astype(float)
    y = np.random.choice(n_classes, size=n).astype(int)

    # with user kwargs
    clf = wrapper_class(model=build_fn, model__hidden_layer_sizes=(100,))
    clf.fit(X, y)
    assert set(clf.get_meta().keys()) == wrapper_class._meta
    # without user kwargs
    def build_fn_no_args(meta, compile_kwargs):
        return build_fn(
            hidden_layer_sizes=(100,), meta=meta, compile_kwargs=compile_kwargs,
        )

    clf = wrapper_class(model=build_fn_no_args)
    clf.fit(X, y)
    assert set(clf.get_meta().keys()) == wrapper_class._meta - {"_user_params"}


def test_model_params_property():
    """Check that the `_model_params` property works as expected.
    """
    clf = KerasRegressor(model="test", model__hidden_layer_sizes=(100,))
    assert clf._model_params == {"hidden_layer_sizes"}


@pytest.mark.parametrize("dest", ["fit", "compile", "predict"])
def test_routing_sets(dest):
    accepted_params = set(inspect.signature(getattr(Model, dest)).parameters.keys()) - {
        "self",
        "kwargs",
    }
    known_params = getattr(BaseWrapper, f"_{dest}_kwargs")
    if LooseVersion(tf.__version__) <= "2.2.0":
        # this parameter is a kwarg in TF 2.2.0
        # it will still work in practice, but breaks this test
        known_params = known_params - {"run_eagerly"}
    assert known_params.issubset(accepted_params)


def test_routed_unrouted_equivalence():
    """Test that `hidden_layer_sizes` and `model__hidden_layer_sizes`
    both work.
    """
    n, d = 20, 3
    n_classes = 3
    X = np.random.uniform(size=(n, d)).astype(float)
    y = np.random.choice(n_classes, size=n).astype(int)

    clf = KerasClassifier(model=dynamic_classifier, model__hidden_layer_sizes=(100,))
    clf.fit(X, y)

    clf = KerasClassifier(model=dynamic_classifier, hidden_layer_sizes=(100,))
    clf.fit(X, y)
