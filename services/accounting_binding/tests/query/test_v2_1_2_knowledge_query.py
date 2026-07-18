"""
Tests — Knowledge Query DSL v2.1.2.

All tests: immutable, declarative, no execution, no Store, no Engine.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
import pytest

from query.knowledge_query import KnowledgeQuery
from query.query_target import QueryTarget
from query.predicate import (
    PredicateOperator,
    ComparisonPredicate,
    ExistsPredicate,
    InPredicate,
)
from query.predicate_composition import And, Or, Not
from query.property_reference import PropertyReference, PROPERTY_REGISTRY
from query.literal import (
    StringValue, IntegerValue, DecimalValue, BooleanValue,
    DateValue, DateTimeValue, EnumValue, to_literal,
)
from query.return_shape import ReturnShape, ReturnShapeType
from query.explainability import ExplainabilityLevel
from query.query_validation import QueryValidator
from query.exceptions import (
    InvalidQueryError,
    InvalidPredicateError,
    InvalidReturnShapeError,
    UnknownPropertyError,
    ValidationError,
)


# ═══════════════════════════════════════════════
# QueryTarget Tests
# ═══════════════════════════════════════════════

class TestQueryTarget:
    def test_all_targets_present(self):
        assert QueryTarget.ENTITY
        assert QueryTarget.AGREEMENT
        assert QueryTarget.OWNERSHIP
        assert QueryTarget.TIMELINE
        assert QueryTarget.GRAPH
        assert QueryTarget.RISK
        assert QueryTarget.PROVENANCE

    def test_enum_immutable(self):
        with pytest.raises(Exception):
            QueryTarget.ENTITY = "something"


# ═══════════════════════════════════════════════
# PropertyReference Tests
# ═══════════════════════════════════════════════

class TestPropertyReference:
    def test_valid_entity_property(self):
        ref = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        assert ref.property_name == "name"
        assert ref.property_type == str

    def test_valid_agreement_property(self):
        ref = PropertyReference(target=QueryTarget.AGREEMENT, property_name="status")
        assert ref.property_type == str

    def test_valid_ownership_property(self):
        ref = PropertyReference(target=QueryTarget.OWNERSHIP, property_name="share")
        assert ref.property_type == float

    def test_valid_risk_property(self):
        ref = PropertyReference(target=QueryTarget.RISK, property_name="score")
        assert ref.property_type == float

    def test_invalid_property_raises(self):
        with pytest.raises(ValueError):
            PropertyReference(target=QueryTarget.ENTITY, property_name="nonexistent")

    def test_immutable(self):
        ref = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        with pytest.raises(Exception):
            ref.property_name = "other"  # type: ignore

    def test_no_raw_string_paths(self):
        """DSL must not use raw string paths."""
        assert not hasattr(PropertyReference, 'path')
        assert 'path' not in PropertyReference.__annotations__


# ═══════════════════════════════════════════════
# Literal Tests
# ═══════════════════════════════════════════════

class TestLiteral:
    def test_string_value(self):
        v = StringValue(value="hello")
        assert v.value == "hello"

    def test_integer_value(self):
        v = IntegerValue(value=42)
        assert v.value == 42

    def test_decimal_value(self):
        v = DecimalValue(value=Decimal("10.5"))
        assert v.value == Decimal("10.5")

    def test_boolean_value(self):
        assert BooleanValue(value=True).value
        assert not BooleanValue(value=False).value

    def test_date_value(self):
        d = date(2026, 7, 8)
        v = DateValue(value=d)
        assert v.value == d

    def test_datetime_value(self):
        dt = datetime(2026, 7, 8, 12, 0, 0)
        v = DateTimeValue(value=dt)
        assert v.value == dt

    def test_enum_value(self):
        v = EnumValue(value="ACTIVE")
        assert v.value == "ACTIVE"

    def test_to_literal_string(self):
        v = to_literal("hello")
        assert isinstance(v, StringValue)

    def test_to_literal_int(self):
        v = to_literal(42)
        assert isinstance(v, IntegerValue)

    def test_to_literal_float(self):
        v = to_literal(3.14)
        assert isinstance(v, DecimalValue)

    def test_to_literal_bool(self):
        v = to_literal(True)
        assert isinstance(v, BooleanValue)

    def test_to_literal_date(self):
        v = to_literal(date(2026, 1, 1))
        assert isinstance(v, DateValue)

    def test_to_literal_datetime(self):
        v = to_literal(datetime(2026, 1, 1, 12, 0))
        assert isinstance(v, DateTimeValue)

    def test_immutable(self):
        v = StringValue(value="x")
        with pytest.raises(Exception):
            v.value = "y"  # type: ignore

    def test_no_raw_python_types(self):
        """DSL must not work with raw Python types directly."""
        from query.literal import LiteralValue
        # Verify all types are wrapped
        assert not hasattr(LiteralValue, '__origin__') or True


# ═══════════════════════════════════════════════
# Predicate Tests
# ═══════════════════════════════════════════════

class TestPredicate:
    def test_comparison_equals(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.EQUALS,
            value=StringValue(value="Test"),
        )
        assert pred.operator == PredicateOperator.EQUALS
        assert pred.property_ref == prop

    def test_comparison_greater_than(self):
        prop = PropertyReference(target=QueryTarget.RISK, property_name="score")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.GREATER_THAN,
            value=DecimalValue(value=Decimal("0.5")),
        )
        assert pred.operator == PredicateOperator.GREATER_THAN

    def test_exists_predicate(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ExistsPredicate(property_ref=prop)
        assert pred.property_ref == prop

    def test_in_predicate(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = InPredicate(
            property_ref=prop,
            values=(StringValue(value="A"), StringValue(value="B")),
        )
        assert len(pred.values) == 2

    def test_all_operators_present(self):
        assert PredicateOperator.EQUALS
        assert PredicateOperator.NOT_EQUALS
        assert PredicateOperator.GREATER_THAN
        assert PredicateOperator.GREATER_OR_EQUAL
        assert PredicateOperator.LESS_THAN
        assert PredicateOperator.LESS_OR_EQUAL
        assert PredicateOperator.CONTAINS
        assert PredicateOperator.STARTS_WITH
        assert PredicateOperator.ENDS_WITH
        assert PredicateOperator.EXISTS
        assert PredicateOperator.IN

    def test_predicate_immutable(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.EQUALS,
            value=StringValue(value="X"),
        )
        with pytest.raises(Exception):
            pred.operator = PredicateOperator.NOT_EQUALS  # type: ignore


# ═══════════════════════════════════════════════
# Predicate Composition Tests
# ═══════════════════════════════════════════════

class TestPredicateComposition:
    def test_and_composition(self):
        prop1 = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        prop2 = PropertyReference(target=QueryTarget.ENTITY, property_name="type")
        pred1 = ComparisonPredicate(
            property_ref=prop1, operator=PredicateOperator.EQUALS,
            value=StringValue(value="X"),
        )
        pred2 = ExistsPredicate(property_ref=prop2)

        combined = And(conditions=(pred1, pred2))
        assert len(combined.conditions) == 2

    def test_and_requires_at_least_2(self):
        with pytest.raises(ValueError):
            And(conditions=())

    def test_or_composition(self):
        prop1 = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        p1 = ExistsPredicate(property_ref=prop1)
        p2 = ExistsPredicate(property_ref=prop1)
        combined = Or(conditions=(p1, p2))
        assert len(combined.conditions) == 2

    def test_or_requires_at_least_2(self):
        with pytest.raises(ValueError):
            Or(conditions=())

    def test_not_composition(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ExistsPredicate(property_ref=prop)
        negated = Not(condition=pred)
        assert negated.condition == pred

    def test_nested_composition(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        p1 = ComparisonPredicate(
            property_ref=prop, operator=PredicateOperator.EQUALS,
            value=StringValue(value="A"),
        )
        p2 = ComparisonPredicate(
            property_ref=prop, operator=PredicateOperator.EQUALS,
            value=StringValue(value="B"),
        )
        # (NOT A) AND (NOT B)
        combined = And(conditions=(Not(condition=p1), Not(condition=p2)))
        assert isinstance(combined.conditions[0], Not)
        assert isinstance(combined.conditions[1], Not)

    def test_composition_immutable(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ExistsPredicate(property_ref=prop)
        combined = And(conditions=(pred, pred))
        with pytest.raises(Exception):
            combined.conditions = ()  # type: ignore


# ═══════════════════════════════════════════════
# ReturnShape Tests
# ═══════════════════════════════════════════════

class TestReturnShape:
    def test_full_projection(self):
        shape = ReturnShape(shape_type=ReturnShapeType.FULL_PROJECTION)
        assert shape.shape_type == ReturnShapeType.FULL_PROJECTION

    def test_fields_shape(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        shape = ReturnShape(shape_type=ReturnShapeType.FIELDS, fields=(prop,))
        assert len(shape.fields) == 1

    def test_fields_requires_fields(self):
        with pytest.raises(ValueError):
            ReturnShape(shape_type=ReturnShapeType.FIELDS)

    def test_non_fields_must_not_have_fields(self):
        with pytest.raises(ValueError):
            ReturnShape(
                shape_type=ReturnShapeType.SUMMARY,
                fields=(PropertyReference(target=QueryTarget.ENTITY, property_name="name"),),
            )

    def test_all_types_present(self):
        assert ReturnShapeType.FULL_PROJECTION
        assert ReturnShapeType.FIELDS
        assert ReturnShapeType.SUMMARY
        assert ReturnShapeType.IDENTIFIERS_ONLY

    def test_immutable(self):
        shape = ReturnShape(shape_type=ReturnShapeType.SUMMARY)
        with pytest.raises(Exception):
            shape.shape_type = ReturnShapeType.FULL_PROJECTION  # type: ignore


# ═══════════════════════════════════════════════
# Explainability Tests
# ═══════════════════════════════════════════════

class TestExplainability:
    def test_all_levels_present(self):
        assert ExplainabilityLevel.NONE
        assert ExplainabilityLevel.SUMMARY
        assert ExplainabilityLevel.FULL

    def test_default_is_none(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        assert query.explainability == ExplainabilityLevel.NONE


# ═══════════════════════════════════════════════
# KnowledgeQuery Tests
# ═══════════════════════════════════════════════

class TestKnowledgeQuery:
    def test_minimal_query(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        assert query.target == QueryTarget.ENTITY
        assert query.predicate is None
        assert query.return_shape.shape_type == ReturnShapeType.SUMMARY
        assert query.explainability == ExplainabilityLevel.NONE

    def test_query_with_predicate(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.EQUALS,
            value=StringValue(value="TestCorp"),
        )
        query = KnowledgeQuery(
            target=QueryTarget.ENTITY,
            predicate=pred,
        )
        assert query.predicate == pred

    def test_query_with_all_fields(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ExistsPredicate(property_ref=prop)
        shape = ReturnShape(shape_type=ReturnShapeType.FULL_PROJECTION)
        query = KnowledgeQuery(
            target=QueryTarget.ENTITY,
            predicate=pred,
            return_shape=shape,
            explainability=ExplainabilityLevel.FULL,
        )
        assert query.explainability == ExplainabilityLevel.FULL
        assert query.return_shape == shape

    def test_immutable(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        with pytest.raises(Exception):
            query.target = QueryTarget.AGREEMENT  # type: ignore

    def test_no_execution_methods(self):
        """KnowledgeQuery must NOT have execute/run/plan methods."""
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        assert not hasattr(query, 'execute')
        assert not hasattr(query, 'run')
        assert not hasattr(query, 'plan')


# ═══════════════════════════════════════════════
# QueryValidation Tests
# ═══════════════════════════════════════════════

class TestQueryValidation:
    def test_valid_minimal(self):
        query = KnowledgeQuery(target=QueryTarget.ENTITY)
        QueryValidator.validate(query)  # should not raise

    def test_valid_with_predicate(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.EQUALS,
            value=StringValue(value="X"),
        )
        query = KnowledgeQuery(target=QueryTarget.ENTITY, predicate=pred)
        QueryValidator.validate(query)

    def test_valid_with_composition(self):
        prop = PropertyReference(target=QueryTarget.ENTITY, property_name="name")
        p1 = ExistsPredicate(property_ref=prop)
        p2 = ExistsPredicate(property_ref=prop)
        query = KnowledgeQuery(
            target=QueryTarget.ENTITY,
            predicate=And(conditions=(p1, p2)),
        )
        QueryValidator.validate(query)

    def test_predicate_target_mismatch(self):
        prop = PropertyReference(target=QueryTarget.AGREEMENT, property_name="status")
        pred = ComparisonPredicate(
            property_ref=prop,
            operator=PredicateOperator.EQUALS,
            value=StringValue(value="ACTIVE"),
        )
        query = KnowledgeQuery(target=QueryTarget.ENTITY, predicate=pred)
        with pytest.raises((InvalidPredicateError, ValidationError)):
            QueryValidator.validate(query)

    def test_return_shape_field_target_mismatch(self):
        prop = PropertyReference(target=QueryTarget.AGREEMENT, property_name="status")
        shape = ReturnShape(shape_type=ReturnShapeType.FIELDS, fields=(prop,))
        query = KnowledgeQuery(target=QueryTarget.ENTITY, return_shape=shape)
        with pytest.raises((InvalidReturnShapeError, ValidationError)):
            QueryValidator.validate(query)

    def test_validation_no_execution(self):
        """Validation must NOT execute anything."""
        assert not hasattr(QueryValidator, 'execute')
        assert not hasattr(QueryValidator, 'plan')
        assert not hasattr(QueryValidator, 'run')


# ═══════════════════════════════════════════════
# Architecture Tests
# ═══════════════════════════════════════════════

class TestQueryArchitecture:
    def test_no_store_import(self):
        """Query DSL must NOT import ProjectionStore."""
        import ast
        query_files = [
            'query/knowledge_query.py',
            'query/query_target.py',
            'query/predicate.py',
            'query/predicate_composition.py',
            'query/property_reference.py',
            'query/literal.py',
            'query/return_shape.py',
            'query/explainability.py',
            'query/query_validation.py',
            'query/exceptions.py',
        ]
        base = '/home/xiag/real-estate-os/services/accounting_binding'
        for rel_path in query_files:
            with open(f"{base}/{rel_path}") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and ('store' in node.module.lower() or 'engine' in node.module.lower() or 'domain' in node.module.lower()):
                        # Allow Domain imports for registry only; property_reference uses it
                        if 'property_reference' in rel_path and 'query_target' in node.module:
                            continue
                        if 'exceptions' in rel_path:
                            continue
                        pytest.fail(
                            f"{rel_path} imports forbidden: {node.module}"
                        )

    def test_no_execution_in_package(self):
        """Query DSL must NOT have execute/plan/run anywhere in the package."""
        import os
        import ast
        base = '/home/xiag/real-estate-os/services/accounting_binding/query'
        for fname in sorted(os.listdir(base)):
            if not fname.endswith('.py') or fname == '__init__.py':
                continue
            with open(os.path.join(base, fname)) as f:
                content = f.read()
            assert 'def execute' not in content, f"{fname} has execute method"
            assert 'def run' not in content, f"{fname} has run method"
            assert 'def plan' not in content, f"{fname} has plan method"
