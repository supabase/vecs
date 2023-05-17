# Hosting

`vecs` is comatible with any Postgres 13+ with the [pgvector](https://github.com/pgvector/pgvector) extension installed.

In the following we show we show instructions for hosting a database on Supabase and locally in docker since both are fast and free.

## Supabase

### Create an account

Create a supabase account at [https://app.supabase.com/sign-up](https://app.supabase.com/sign-up).

![sign up](./assets/supabase_sign_up.png)

### Create a new project

Select `New Project`

![new_project_promp](./assets/supabase_new_project_prompt.png)

Complete the prompts. Be sure to remember or write down your password as we'll need that when connecting with vecs.

![new_project](./assets/supabase_new_project.png)

### Connection Info

On the project page, navigate to `Settings` > `Database` > `Database Settings`

![connection_info](./assets/supabase_connection_info.png)

and substitue those fields into the conenction string

```
postgresql://<user>:<password>@<host>:<port>/<db_name>
```
i.e.
```
postgres://postgres:[YOUR PASSWORD]@db.cvykdyhlwwwojivopztl.supabase.co:5432/postgres
```

Keep that connection string secret and safe. Its your `DB_CONNECTION` in the [quickstart guide](api.md),


## Docker

Install docker if you don't have it already at [Get Docker](https://docs.docker.com/get-docker/)


### Start the Postgres Container

Next, run
```sh
docker run --rm -d \
    --name vecs_hosting_guide \
    -p 5019:5432 \
    -e POSTGRES_DB=vecs_db \
    -e POSTGRES_PASSWORD=password \
    -e POSTGRES_USER=postgres \
    supabase/postgres:15.1.0.74
```

### Connection Info

Substitue the values from the previous section into the postgres conenction string

```
postgresql://<user>:<password>@<host>:<port>/<db_name>
```
i.e.
```
postgresql://postgres:password@localhost:5019/vecs_db
```

Keep that connection string secret and safe. Its your `DB_CONNECTION` in the [quickstart guide](api.md),