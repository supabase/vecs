from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import sessionmaker

from vecs.exc import CollectionNotFound

if TYPE_CHECKING:
    from vecs.collection import Collection


class Client:
    def __init__(self, connection_string):
        self.engine = create_engine(connection_string)
        self.meta = MetaData(schema="vecs")
        self.Session = sessionmaker(self.engine)

        with self.Session() as sess:
            with sess.begin():
                sess.execute(text("create schema if not exists vecs;"))
                sess.execute(text("create extension if not exists vector;"))

    def create_collection(self, name: str, dimension: int) -> Collection:
        """Create a collection"""
        from vecs.collection import Collection

        return Collection(name, dimension, self)._create()

    def get_collection(self, name: str) -> Collection:
        """Get an existing collection"""
        from vecs.collection import Collection

        collections = Collection._list_collections(self)
        for collection in collections:
            if collection.name == name:
                return collection
        raise CollectionNotFound("No collection found with requested name")

    def list_collections(self) -> List["Collection"]:
        """List all collections"""
        from vecs.collection import Collection

        return Collection._list_collections(self)

    def delete_collection(self, name: str) -> None:
        """List all collections"""
        from vecs.collection import Collection

        Collection(name, -1, self)._drop()
        return
