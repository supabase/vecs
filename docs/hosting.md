# Deployment


`vecs` is comatible with any Postgres 13+ with the [pgvector](https://github.com/pgvector/pgvector) extension installed.

In the following we show we show instructions for hosting a database on Supabase and locally in docker since both are fast and free.


## Supabase

### Cloud Hosted

#### Create an account

Create a supabase account at [https://app.supabase.com/sign-up](https://app.supabase.com/sign-up).

![sign up](./assets/supabase_sign_up.png)

#### Create a new project

Select `New Project`

![new_project_promp](./assets/supabase_new_project_prompt.png)

Complete the prompts. Be sure to remember or write down your password as we'll need that when connecting with vecs.

![new_project](./assets/supabase_new_project.png)

#### Connection Info

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


### Local

You can also use Supabase locally on your machine. Doing so will keep your project setup consistent when deploying to hosted Supabase.

### Install the CLI

To install the CLI, use the relevant system instructions below

=== "macOS"

    ```
    brew install supabase/tap/supabase
    ```

=== "Windows"

    ```
    scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
    scoop install supabase
    ```

=== "Linux"

    Linux packages are provided in Releases. To install, download the .apk/.deb/.rpm file depending on your package manager and run one of the following:

    ```
    sudo apk add --allow-untrusted <...>.apk
    ```
    or
    ```
    sudo dpkg -i <...>.deb
    ```
    or
    ```
    sudo rpm -i <...>.rpm
    ```

=== "npm"

    ```
    npm install supabase --save-dev
    ```

### Start the Project

From your project directory, create the `supabase/` sub-directory required for supabase projects by running:

```sh
supabase init
```

next start the application using:

```
supabase start
```

which will download the latest Supabase containers and provide a URL to each service:

```
Seeding data supabase/seed.sql...me...
Started supabase local development setup.

         API URL: http://localhost:54321
     GraphQL URL: http://localhost:54321/graphql/v1
          DB URL: postgresql://postgres:postgres@localhost:54322/postgres
      Studio URL: http://localhost:54323
    Inbucket URL: http://localhost:54324
      JWT secret: super-secret-jwt-token-with-at-least-32-characters-long
        anon key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFz
service_role key: eyJhbGciOiJIUzI1NiIsInR5cClJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU
```

The service we need for `vecs` is `DB URL`. Note it down for use as our `DB_CONNECTION`

```
postgresql://<user>:<password>@<host>:<port>/<db_name>
```

For more info on running a local Supabase project, checkout the [Supabase CLI guide](https://supabase.com/docs/guides/cli)

## Docker

Install docker if you don't have it already at [Get Docker](https://docs.docker.com/get-docker/)


#### Start the Postgres Container

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

#### Connection Info
Substitue the values from the previous section into the postgres conenction string

```
postgresql://<user>:<password>@<host>:<port>/<db_name>
```
i.e.
```
postgresql://postgres:password@localhost:5019/vecs_db
```

Keep that connection string secret and safe. Its your `DB_CONNECTION` in the [quickstart guide](api.md)
