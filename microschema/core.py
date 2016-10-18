# -*- coding: utf-8 -*-
from __future__ import absolute_import


class ValidationError(ValueError):
    pass

class ConversionError(ValueError):
    pass


messages = {
    'input': u'input {name} must be a dictionary instance, got: {type}.',
    'rogue': u'Rogue field.',
    'missing': u'Missing required field.',
    'field': u'Field must be a {schema_type} instance, got: {field_type}.',
    'none': u'Field must be None, got: {field_type}.',
    'schema': u'Missing schema definition.',
}


def validate(schema, data, context=None):
    """Validates data based on a given schema."""
    return Validator(schema, data, context).validate()


class Validator(object):
    """Validator performs data validation.
    """

    def __init__(self, schema, data, context):
        self._schema = schema
        self._data = data
        self._context = context

    def validate(self):
        if not isinstance(self._schema, dict):
            instance_type = type(self._schema).__name__
            message = messages['input']
            raise TypeError(message.format(name='schema', type=instance_type))

        if not isinstance(self._data, dict):
            instance_type = type(self._data).__name__
            message = messages['input']
            raise TypeError(message.format(name='data', type=instance_type))

        errors = {}
        self._report_rouge_fields(errors)

        # validate each field in the schema
        for name, defs in self._schema.iteritems():
            self._validate_field(name, defs, errors)

        if errors:
            raise ValidationError(errors)

        return self._data

    def _validate_field(self, name, defs, errors):
        field = self._data.get(name)

        if self._is_field_missing(name):
            if self._is_field_required(defs):
                errors.update({name: messages['missing']})
            return

        # validate field
        validator = defs.get('validator', default_validator)
        try:
            validator(name, defs, self._data, field, context=self._context)
        except ValidationError as e:
            errors.update({name: e.message})

    def _is_field_required(self, defs):
        return defs.get('required', False)

    def _is_field_missing(self, name):
        return name not in self._data

    def _report_rouge_fields(self, errors):
        for field in self._get_rouge_fields():
            errors.update({field: messages['rogue']})

    def _get_schema_fields(self):
        return set(self._schema.keys())

    def _get_data_fields(self):
        return set(self._data.keys())

    def _get_rouge_fields(self):
        return self._get_data_fields() - self._get_schema_fields()


def convert(schema, data, validated=False):
    """Convert data based on a given schema."""

    if not validated:
        validate(schema, data)

    errors = {}
    converted_data = {}

    # convert each field in the schema
    for name, defs in schema.iteritems():
	if not defs.get('required', False) and name not in data:
	    continue
	
	field = data.get(name)
        
	# convert field
        converter = defs.get('converter', default_converter)
        try:
            converted_data[name] = converter(defs, data, field)
        except ConversionError as e:
            errors.update({name: e.message})

    if errors:
        raise ConversionError(errors)

    return converted_data


def default_validator(name, defs, data, value, context=None):
    schema_type = defs['type']
    compound_type = defs.get('compound_type')

    if schema_type is None:
        if value is not None:
            message = messages['none'].format(
                field_type=type(value).__name__,
            )
            raise ValidationError(message)
        else:
            return value

    if not isinstance(value, schema_type):
        message = messages['field'].format(
            schema_type=schema_type.__name__,
            field_type=type(value).__name__,
        )
        raise ValidationError(message)

    if schema_type == dict:
        validate(defs['schema'], value)

    errors = {}
    if schema_type == list:
        for index, item in enumerate(value):
            try:
                if compound_type is not None:
                    compound_defs = {'type': compound_type}
                    default_validator(index, compound_defs, value, item)
                    continue
                schema = defs['schema']
                validate(schema, item)
            except KeyError as e:
                errors.update({index: messages['schema']})
            except (TypeError, ValidationError) as e:
                errors.update({index: e.message})

    if errors:
        raise ValidationError(errors)

    return value


def default_converter(defs, data, value):
    compound_type = defs.get('compound_type')
    if compound_type is not None:
        schema_type = compound_type
    else:
        try:
            schema_type = defs['type']
        except KeyError as e:
            return value

    if schema_type == dict:
        return convert(defs['schema'], value)

    errors = {}
    converted_data = []
    if schema_type == list:
        for index, item in enumerate(value):
            try:
                converted_data.append(convert(defs['schema'], item))
            except ConversionError as e:
                errors.update({index: e.message})
        return converted_data

    if errors:
        raise ConversionError(errors)

    return value
