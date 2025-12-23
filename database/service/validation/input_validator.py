"""Input validation layer for request parameters.

This module provides input-level validation that performs fast-fail checks
on incoming request parameters before any database operations. Validates
data types, ranges, and formats.

Attributes:
    InputValidator: Validates incoming request parameters and DTOs.
"""

from typing import Any, List, Optional, Dict, Type
from datetime import datetime, date

from database.service.base import ValidationException


class InputValidator:
    """Validates input parameters and request DTOs.

    Provides validation for common parameter types including strings,
    numbers, dates, enums, and collections. Designed for fast-fail before
    database operations.
    """

    @staticmethod
    def validate_place_id(place_id: Any) -> int:
        """Validate and cast place ID parameter.

        Args:
            place_id: The place ID to validate.

        Returns:
            The validated place_id as integer.

        Raises:
            ValidationException: If place_id is None, negative, or invalid.
        """
        if place_id is None:
            raise ValidationException(
                "Place ID cannot be None",
                field="place_id",
                value=place_id,
                context={"requirement": "required field"},
            )

        try:
            place_id_int = int(place_id)
        except (ValueError, TypeError) as e:
            raise ValidationException(
                f"Place ID must be integer, got {type(place_id).__name__}",
                field="place_id",
                value=place_id,
                context={"expected_type": "int"},
            ) from e

        if place_id_int <= 0:
            raise ValidationException(
                f"Place ID must be positive, got {place_id_int}",
                field="place_id",
                value=place_id_int,
                context={"constraint": "place_id > 0"},
            )

        return place_id_int

    @staticmethod
    def validate_review_id(review_id: Any) -> int:
        """Validate and cast review ID parameter.

        Args:
            review_id: The review ID to validate.

        Returns:
            The validated review_id as integer.

        Raises:
            ValidationException: If review_id is None, negative, or invalid.
        """
        if review_id is None:
            raise ValidationException(
                "Review ID cannot be None",
                field="review_id",
                value=review_id,
                context={"requirement": "required field"},
            )

        try:
            review_id_int = int(review_id)
        except (ValueError, TypeError) as e:
            raise ValidationException(
                f"Review ID must be integer, got {type(review_id).__name__}",
                field="review_id",
                value=review_id,
                context={"expected_type": "int"},
            ) from e

        if review_id_int <= 0:
            raise ValidationException(
                f"Review ID must be positive, got {review_id_int}",
                field="review_id",
                value=review_id_int,
                context={"constraint": "review_id > 0"},
            )

        return review_id_int

    @staticmethod
    def validate_text_length(
        text: Any,
        field_name: str = "text",
        min_length: int = 1,
        max_length: int = 10000,
    ) -> str:
        """Validate text parameter length.

        Args:
            text: The text to validate.
            field_name: Name of field for error messages.
            min_length: Minimum allowed length (default: 1).
            max_length: Maximum allowed length (default: 10000).

        Returns:
            The validated text string.

        Raises:
            ValidationException: If text is None, invalid type, or wrong length.
        """
        if text is None:
            raise ValidationException(
                f"{field_name} cannot be None",
                field=field_name,
                value=text,
                context={"requirement": "required field"},
            )

        if not isinstance(text, str):
            raise ValidationException(
                f"{field_name} must be string, got {type(text).__name__}",
                field=field_name,
                value=text,
                context={"expected_type": "str"},
            )

        text = text.strip()

        if len(text) < min_length:
            raise ValidationException(
                f"{field_name} too short: {len(text)} < {min_length}",
                field=field_name,
                value=text,
                context={
                    "constraint": f"length >= {min_length}",
                    "actual_length": len(text),
                },
            )

        if len(text) > max_length:
            raise ValidationException(
                f"{field_name} too long: {len(text)} > {max_length}",
                field=field_name,
                value=f"{text[:50]}...",
                context={
                    "constraint": f"length <= {max_length}",
                    "actual_length": len(text),
                },
            )

        return text

    @staticmethod
    def validate_numeric_range(
        value: Any,
        field_name: str = "value",
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> float:
        """Validate numeric value is within range.

        Args:
            value: The numeric value to validate.
            field_name: Name of field for error messages.
            min_value: Minimum allowed value (inclusive, None=no limit).
            max_value: Maximum allowed value (inclusive, None=no limit).

        Returns:
            The validated value as float.

        Raises:
            ValidationException: If value is None, invalid type, or out of range.
        """
        if value is None:
            raise ValidationException(
                f"{field_name} cannot be None",
                field=field_name,
                value=value,
                context={"requirement": "required field"},
            )

        try:
            numeric_value = float(value)
        except (ValueError, TypeError) as e:
            raise ValidationException(
                f"{field_name} must be numeric, got {type(value).__name__}",
                field=field_name,
                value=value,
                context={"expected_type": "float"},
            ) from e

        if min_value is not None and numeric_value < min_value:
            raise ValidationException(
                f"{field_name} below minimum: {numeric_value} < {min_value}",
                field=field_name,
                value=numeric_value,
                context={
                    "constraint": f"value >= {min_value}",
                    "actual_value": numeric_value,
                },
            )

        if max_value is not None and numeric_value > max_value:
            raise ValidationException(
                f"{field_name} above maximum: {numeric_value} > {max_value}",
                field=field_name,
                value=numeric_value,
                context={
                    "constraint": f"value <= {max_value}",
                    "actual_value": numeric_value,
                },
            )

        return numeric_value

    @staticmethod
    def validate_date_range(
        start_date: Any,
        end_date: Any,
        field_name: str = "date_range",
    ) -> tuple[date, date]:
        """Validate date range is valid and chronological.

        Args:
            start_date: Start date (datetime, date, or ISO string).
            end_date: End date (datetime, date, or ISO string).
            field_name: Name of field for error messages.

        Returns:
            Tuple of (start_date, end_date) as date objects.

        Raises:
            ValidationException: If dates are None, invalid, or end < start.
        """
        if start_date is None or end_date is None:
            raise ValidationException(
                f"{field_name} cannot be None",
                field=field_name,
                value=(start_date, end_date),
                context={"requirement": "both dates required"},
            )

        # Convert to date objects
        if isinstance(start_date, datetime):
            start_date_obj = start_date.date()
        elif isinstance(start_date, date):
            start_date_obj = start_date
        elif isinstance(start_date, str):
            try:
                start_date_obj = datetime.fromisoformat(
                    start_date.split('T')[0]
                ).date()
            except (ValueError, AttributeError) as e:
                raise ValidationException(
                    f"start_date invalid ISO format: {start_date}",
                    field="start_date",
                    value=start_date,
                    context={"expected_format": "YYYY-MM-DD or ISO string"},
                ) from e
        else:
            raise ValidationException(
                f"start_date invalid type: {type(start_date).__name__}",
                field="start_date",
                value=start_date,
                context={"expected_types": ["date", "datetime", "str"]},
            )

        # Convert to date objects
        if isinstance(end_date, datetime):
            end_date_obj = end_date.date()
        elif isinstance(end_date, date):
            end_date_obj = end_date
        elif isinstance(end_date, str):
            try:
                end_date_obj = datetime.fromisoformat(
                    end_date.split('T')[0]
                ).date()
            except (ValueError, AttributeError) as e:
                raise ValidationException(
                    f"end_date invalid ISO format: {end_date}",
                    field="end_date",
                    value=end_date,
                    context={"expected_format": "YYYY-MM-DD or ISO string"},
                ) from e
        else:
            raise ValidationException(
                f"end_date invalid type: {type(end_date).__name__}",
                field="end_date",
                value=end_date,
                context={"expected_types": ["date", "datetime", "str"]},
            )

        if end_date_obj < start_date_obj:
            raise ValidationException(
                f"end_date before start_date: {end_date_obj} < "
                f"{start_date_obj}",
                field=field_name,
                value=(start_date_obj, end_date_obj),
                context={
                    "constraint": "end_date >= start_date",
                    "start": start_date_obj.isoformat(),
                    "end": end_date_obj.isoformat(),
                },
            )

        return (start_date_obj, end_date_obj)

    @staticmethod
    def validate_list_not_empty(
        items: Any,
        field_name: str = "items",
        item_type: Optional[Type] = None,
    ) -> List[Any]:
        """Validate list is not None or empty.

        Args:
            items: The list to validate.
            field_name: Name of field for error messages.
            item_type: Optional type to validate each item.

        Returns:
            The validated list.

        Raises:
            ValidationException: If items is None, not a list, or empty.
        """
        if items is None:
            raise ValidationException(
                f"{field_name} cannot be None",
                field=field_name,
                value=items,
                context={"requirement": "required field"},
            )

        if not isinstance(items, list):
            raise ValidationException(
                f"{field_name} must be list, got {type(items).__name__}",
                field=field_name,
                value=items,
                context={"expected_type": "list"},
            )

        if len(items) == 0:
            raise ValidationException(
                f"{field_name} cannot be empty",
                field=field_name,
                value=items,
                context={"constraint": "list length > 0"},
            )

        if item_type is not None:
            invalid_items = [
                (i, item) for i, item in enumerate(items)
                if not isinstance(item, item_type)
            ]
            if invalid_items:
                invalid_str = ", ".join(
                    f"[{i}]={v}" for i, v in invalid_items[:3]
                )
                raise ValidationException(
                    f"{field_name} contains invalid items: {invalid_str}",
                    field=field_name,
                    value=invalid_str,
                    context={
                        "expected_item_type": item_type.__name__,
                        "invalid_count": len(invalid_items),
                    },
                )

        return items

    @staticmethod
    def validate_enum_value(
        value: Any,
        allowed_values: List[str],
        field_name: str = "enum_field",
    ) -> str:
        """Validate value is in allowed enum list.

        Args:
            value: The value to validate.
            allowed_values: List of allowed values.
            field_name: Name of field for error messages.

        Returns:
            The validated value as string.

        Raises:
            ValidationException: If value is None or not in allowed list.
        """
        if value is None:
            raise ValidationException(
                f"{field_name} cannot be None",
                field=field_name,
                value=value,
                context={"requirement": "required field"},
            )

        value_str = str(value)

        if value_str not in allowed_values:
            raise ValidationException(
                f"{field_name} invalid: '{value_str}' not in "
                f"{allowed_values}",
                field=field_name,
                value=value_str,
                context={
                    "allowed_values": allowed_values,
                    "provided_value": value_str,
                },
            )

        return value_str

    @staticmethod
    def validate_score_range(
        score: Any,
        field_name: str = "score",
        min_score: float = 0.0,
        max_score: float = 1.0,
    ) -> float:
        """Validate score is within typical 0-1 or 0-5 range.

        Args:
            score: The score to validate.
            field_name: Name of field for error messages.
            min_score: Minimum allowed score (default: 0.0).
            max_score: Maximum allowed score (default: 1.0).

        Returns:
            The validated score as float.

        Raises:
            ValidationException: If score invalid or out of range.
        """
        return InputValidator.validate_numeric_range(
            score, field_name, min_score, max_score
        )


__all__ = ["InputValidator"]
