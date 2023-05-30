import typing as t
import pipeman.entity.fields as fields
from pipeman.util.errors import DataTypeNotSupportedError
from autoinject import injector


class GenericFactory:

    def __init__(self, field_list: t.Iterable = None):
        self.factory_name = type(self)
        self._field_list = {}
        if field_list:
            for field in field_list:
                self._field_list[getattr(field, "DATA_TYPE")] = field

    def build_field(self, field_name: str, data_type: str, field_config: dict, container_type: str, container_id: int) -> t.Optional[fields.Field]:
        if data_type in self._field_list:
            return self._field_list[data_type](field_name, field_config, container_type, container_id)


class _BuiltInFactory(GenericFactory):

    def __init__(self):
        import pipeman.entity.entity_field as ef
        super().__init__([
            fields.BooleanField,
            fields.DateField,
            fields.DateTimeField,
            fields.DecimalField,
            fields.EmailField,
            fields.FloatField,
            fields.IntegerField,
            fields.ChoiceField,
            fields.TextField,
            fields.MultiLineTextField,
            fields.TelephoneField,
            fields.TimeField,
            fields.URLField,
            #fields.CompositeField,
            fields.KeyValueField,
            ef.EntityReferenceField,
            ef.ComponentReferenceField,
            fields.VocabularyReferenceField,
            fields.DatasetReferenceField
        ])


@injector.injectable_global
class FieldCreator:

    def __init__(self):
        self._factories = {}
        self.register_factory(_BuiltInFactory())

    def register_factory(self, factory: GenericFactory):
        self._factories[factory.factory_name] = factory

    def build_field(self, field_name: str, data_type: str, field_config: dict, container_type: str, container_id: int = None) -> fields.Field:
        for fact in self._factories.values():
            field = fact.build_field(field_name, data_type, field_config, container_type, container_id)
            if field:
                return field
        raise DataTypeNotSupportedError(data_type)
