from typing import Any, Dict, Generic, List, NewType, Tuple, Type, TypeVar, Union

from pydantic import BaseModel
from tortoise.expressions import Q
from tortoise.models import Model

Total = NewType("Total", int)
ModelType = TypeVar("ModelType", bound=Model)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def _model_field_names(self) -> set[str]:
        meta = getattr(self.model, "_meta", None)
        fields = set(getattr(meta, "fields", set()) or set())
        if not fields:
            return set()
        m2m_fields = set(getattr(meta, "m2m_fields", set()) or set())
        pk_attr = getattr(meta, "pk_attr", "id") or "id"
        return fields - m2m_fields - {pk_attr, "id"}

    def _filter_model_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        field_names = self._model_field_names()
        if not field_names:
            return dict(data)
        return {key: value for key, value in data.items() if key in field_names}

    async def get(self, id: int) -> ModelType:
        return await self.model.get(id=id)

    async def list(self, page: int, page_size: int, search: Q = Q(), order: list = []) -> Tuple[Total, List[ModelType]]:
        query = self.model.filter(search)
        return await query.count(), await query.offset((page - 1) * page_size).limit(page_size).order_by(*order)

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        if isinstance(obj_in, dict):
            obj_dict = obj_in
        elif hasattr(obj_in, "create_dict"):
            obj_dict = obj_in.create_dict()
        else:
            obj_dict = obj_in.model_dump()
        obj_dict = self._filter_model_fields(obj_dict)
        obj = self.model(**obj_dict)
        await obj.save()
        return obj

    async def update(self, id: int, obj_in: Union[UpdateSchemaType, Dict[str, Any]]) -> ModelType:
        if isinstance(obj_in, dict):
            obj_dict = obj_in
        elif hasattr(obj_in, "update_dict"):
            obj_dict = obj_in.update_dict()
        else:
            obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        obj_dict = self._filter_model_fields(obj_dict)
        obj = await self.get(id=id)
        obj = obj.update_from_dict(obj_dict)
        await obj.save()
        return obj

    async def remove(self, id: int) -> None:
        obj = await self.get(id=id)
        await obj.delete()
