# Metadata

vecs allows you to associate key-value pairs of metadata with indexes and ids in your collections.
You can then add filters to queries that reference the metadata metadata.

## Types
Metadata is stored as binary JSON. As a result, allowed metadata types are drawn from JSON primitive types.

- Boolean
- String
- Number

The technical limit of a metadata field associated with a vector is 1GB.
In practice you should keep metadata fields as small as possible to maximize performance.

## Metadata Query Language

The metadata query language is based loosely on [mongodb's selectors](https://www.mongodb.com/docs/manual/reference/operator/query/).

`vecs` currently supports a subset of those operators.


### Comparison Operators

Comparison operators compare a provided value with a value stored in metadata field of the vector store.

| Operator  | Description |
| --------- | ----------- |
| $eq       | Matches values that are equal to a specified value |
| $gt       | Matches values that are greater than a specified value |
| $gte      | Matches values that are greater than or equal to a specified value |
| $lt       | Matches values that are less than a specified value |
| $lte      | Matches values that are less than or equal to a specified value |


### Logical Operators

Logical operators compose other operators, and can be nested.

| Operator  | Description |
| --------- | ----------- |
| $and      |  Joins query clauses with a logical AND returns all documents that match the conditions of both clauses. |
| $or       |  Joins query clauses with a logical OR returns all documents that match the conditions of either clause. |


### Examples

---

`year` equals 2020

```json
{"year": {"$eq": 2020}}
```

---

`year` equals 2020 or `gross` greater than or equal to 5000.0

```json
{
    "$or": [
        {"year": {"$eq": 2020}},
        {"gross": {"$gte": 5000.0}}
    ]
}
```

---

`last_name` is less than "Brown" and `is_priority_customer` is true

```json
{
    "$and": [
        {"last_name": {"$lt": "Brown"}},
        {"is_priority_customer": {"$gte": 5000.00}}
    ]
}
```