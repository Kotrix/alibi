import numpy as np
import tensorflow as tf

from typing import Callable, Union, Tuple


numerical_gradients = {'pytorch': [], 'tensorflow': []}
"""
dict: A registry for numerical gradient functions implemented in PyTorch or TensorFlow. This should be imported by
backend classes that need to utilize numerical differentiation. To add a function to the registry, import the
`numerical_gradient` decorator from `alibi.utils.gradients` and parametrize it by with the `framework` argument that
takes values 'pytorch'/'tensorflow'.
"""


def numerical_gradient(framework='tensorflow'):
    """
    A decorator used to register a function as a numerical gradient implementation.
    """
    def decorate_numerical_gradient(func):
        func.optimizer = framework
        numerical_gradients[framework].append(func)
        return func
    return decorate_numerical_gradient


def perturb(X: np.ndarray,
            eps: Union[float, np.ndarray] = 1e-08,
            proba: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply perturbation to instance or prediction probabilities. Used for numerical calculation of gradients.

    Parameters
    ----------
    X
        Array to be perturbed
    eps
        Size of perturbation
    proba
        If True, the net effect of the perturbation needs to be 0 to keep the sum of the probabilities equal to 1

    Returns
    -------
    Instances where a positive and negative perturbation is applied.
    """

    # N = batch size; F = nb of features in X
    shape = X.shape
    X = np.reshape(X, (shape[0], -1))  # NxF
    dim = X.shape[1]  # F
    pert = np.tile(np.eye(dim) * eps, (shape[0], 1))  # (N*F)xF
    if proba:
        eps_n = eps / (dim - 1)
        pert += np.tile((np.eye(dim) - np.ones((dim, dim))) * eps_n, (shape[0], 1))  # (N*F)xF
    X_rep = np.repeat(X, dim, axis=0)  # (N*F)xF
    X_pert_pos, X_pert_neg = X_rep + pert, X_rep - pert
    shape = (dim * shape[0],) + shape[1:]
    X_pert_pos = np.reshape(X_pert_pos, shape)  # (N*F)x(shape of X[0])
    X_pert_neg = np.reshape(X_pert_neg, shape)  # (N*F)x(shape of X[0])

    return X_pert_pos, X_pert_neg


def num_grad_batch(func: Callable,
                   X: np.ndarray,
                   args: Tuple = (),
                   eps: Union[float, np.ndarray] = 1e-08) -> np.ndarray:
    """
    Calculate the numerical gradients of a vector-valued function (typically a prediction function in classification)
    with respect to a batch of arrays X.

    Parameters
    ----------
    func
        Function to be differentiated
    X
        A batch of vectors at which to evaluate the gradient of the function.
    args
        Any additional arguments to pass to the function
    eps
        Gradient step to use in the numerical calculation, can be a single float or one for each feature

    Returns
    -------
    An array of gradients at each point in the batch X

    """
    # N = gradient batch size; F = nb of features in X, P = nb of prediction classes, B = instance batch size

    batch_size = X.shape[0]
    data_shape = X[0].shape
    preds = func(X, *args)
    preds = tf.reshape(preds, (-1, 1))
    X_pert_pos, X_pert_neg = perturb(X, eps)  # (N*F)x(shape of X[0])
    X_pert = np.concatenate([X_pert_pos, X_pert_neg], axis=0)
    preds_concat = func(X_pert, *args)  # make predictions
    preds_concat = preds_concat.numpy()
    preds_concat = preds_concat.reshape(-1, 1)
    n_pert = X_pert_pos.shape[0]

    grad_numerator = preds_concat[:n_pert] - preds_concat[n_pert:]  # (N*F)*P
    grad_numerator = np.reshape(np.reshape(grad_numerator, (batch_size, -1)),
                                (batch_size, preds.shape[1], -1), order='F')  # NxPxF

    grad = grad_numerator / (2 * eps)  # NxPxF
    grad = grad.reshape(preds.shape + data_shape)  # BxPx(shape of X[0])

    return grad
