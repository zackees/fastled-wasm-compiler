"""Functor-based test validators for integration tests."""

from .base import Functor
from .compilation import BuildFlagsVerificationFunctor, CompilationSuccessFunctor
from .output import ManifestExistsFunctor, WASMFileSizeFunctor
from .pch import PCHDisabledFunctor, PCHEnabledFunctor

__all__ = [
    "Functor",
    "PCHEnabledFunctor",
    "PCHDisabledFunctor",
    "WASMFileSizeFunctor",
    "ManifestExistsFunctor",
    "CompilationSuccessFunctor",
    "BuildFlagsVerificationFunctor",
]
