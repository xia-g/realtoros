"""
QueryValidation — validates query structure without executing.

Checks:
- mandatory Target
- valid PropertyReference
- compatible Predicate
- compatible ReturnShape
"""
from __future__ import annotations

from typing import Optional

from query.knowledge_query import KnowledgeQuery
from query.query_target import QueryTarget
from query.predicate import Predicate, ComparisonPredicate, ExistsPredicate, InPredicate, PredicateOperator
from query.predicate_composition import And, Or, Not, QueryPredicate, ComposedPredicate
from query.property_reference import PropertyReference
from query.return_shape import ReturnShape, ReturnShapeType
from query.exceptions import InvalidQueryError, InvalidPredicateError, InvalidReturnShapeError, ValidationError

# Operators that work with string properties
_STRING_OPS = {
    PredicateOperator.EQUALS,
    PredicateOperator.NOT_EQUALS,
    PredicateOperator.CONTAINS,
    PredicateOperator.STARTS_WITH,
    PredicateOperator.ENDS_WITH,
    PredicateOperator.IN,
}

# Operators that work with numeric properties
_NUMERIC_OPS = {
    PredicateOperator.EQUALS,
    PredicateOperator.NOT_EQUALS,
    PredicateOperator.GREATER_THAN,
    PredicateOperator.GREATER_OR_EQUAL,
    PredicateOperator.LESS_THAN,
    PredicateOperator.LESS_OR_EQUAL,
    PredicateOperator.IN,
}


class QueryValidator:
    """Сервис проверки корректности Query.

    Validation ничего не исполняет.
    """

    @staticmethod
    def validate(query: KnowledgeQuery) -> None:
        """Validate a KnowledgeQuery. Raises ValidationError on failure."""
        errors: list[str] = []

        # 1. Target is mandatory
        if query.target is None:
            errors.append("Query target is required")

        # 2. Validate predicate tree
        if query.predicate is not None:
            try:
                QueryValidator._validate_predicate(query.predicate, query.target)
            except (InvalidPredicateError, InvalidQueryError) as e:
                errors.append(str(e))

        # 3. Validate return shape
        try:
            QueryValidator._validate_return_shape(query.return_shape, query.target)
        except InvalidReturnShapeError as e:
            errors.append(str(e))

        if errors:
            raise ValidationError("; ".join(errors))

    @staticmethod
    def _validate_predicate(predicate: QueryPredicate, target: QueryTarget) -> None:
        """Recursively validate a predicate tree."""
        # Composed predicates
        if isinstance(predicate, And):
            for c in predicate.conditions:
                QueryValidator._validate_predicate(c, target)
        elif isinstance(predicate, Or):
            for c in predicate.conditions:
                QueryValidator._validate_predicate(c, target)
        elif isinstance(predicate, Not):
            QueryValidator._validate_predicate(predicate.condition, target)
        # Leaf predicates
        elif isinstance(predicate, ComparisonPredicate):
            QueryValidator._validate_comparison(predicate, target)
        elif isinstance(predicate, ExistsPredicate):
            QueryValidator._validate_property(predicate.property_ref, target)
        elif isinstance(predicate, InPredicate):
            QueryValidator._validate_property(predicate.property_ref, target)
        else:
            raise InvalidPredicateError(f"Unknown predicate type: {type(predicate).__name__}")

    @staticmethod
    def _validate_comparison(predicate: ComparisonPredicate, target: QueryTarget) -> None:
        """Validate a comparison predicate."""
        QueryValidator._validate_property(predicate.property_ref, target)
        prop_type = predicate.property_ref.property_type

        # Check operator compatibility with property type
        op = predicate.operator
        if op not in _STRING_OPS and op not in _NUMERIC_OPS:
            raise InvalidPredicateError(f"Unknown operator: {op.name}")

        if op in _STRING_OPS and prop_type not in (str, list):
            raise InvalidPredicateError(
                f"Operator {op.name} is not compatible with property type {prop_type.__name__}"
            )

    @staticmethod
    def _validate_property(prop: PropertyReference, target: QueryTarget) -> None:
        """Validate property reference matches target."""
        if prop.target != target:
            raise InvalidPredicateError(
                f"Property '{prop.property_name}' targets {prop.target.name}, "
                f"but query targets {target.name}"
            )

    @staticmethod
    def _validate_return_shape(shape: ReturnShape, target: QueryTarget) -> None:
        """Validate return shape."""
        if shape.shape_type == ReturnShapeType.FIELDS:
            for field in shape.fields:
                if field.target != target:
                    raise InvalidReturnShapeError(
                        f"Field '{field.property_name}' targets {field.target.name}, "
                        f"but query targets {target.name}"
                    )
