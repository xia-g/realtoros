"""Projection layer custom exceptions."""
from __future__ import annotations


class ProjectionError(Exception):
    """Base projection layer error."""


class ProjectionNotFoundError(ProjectionError):
    """Projection not found in store."""


class ProjectionBuilderNotFoundError(ProjectionError):
    """No builder registered for the requested ProjectionType."""


class ProjectionBuildError(ProjectionError):
    """Projection build failed."""


class BuildPlanError(ProjectionError):
    """Invalid build plan."""


class DuplicateProjectionError(ProjectionError):
    """Projection already exists in store."""
