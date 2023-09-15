# pylint: disable=redefined-outer-name,no-member

import json
import os
import subprocess
import time
from typing import Generator

import pytest
from parse import parse
from sqlalchemy import create_engine, text

import vecs

PYTEST_DB = "postgresql://postgres:password@localhost:5611/vecs_db"


@pytest.fixture(scope="session")
def maybe_start_pg() -> Generator[None, None, None]:
    """Creates a postgres 15 docker container that can be connected
    to using the PYTEST_DB connection string"""

    container_name = "vecs_pg"
    image = "supabase/postgres:15.1.0.118"

    connection_template = "postgresql://{user}:{pw}@{host}:{port:d}/{db}"
    conn_args = parse(connection_template, PYTEST_DB)

    if "GITHUB_SHA" in os.environ:
        yield
        return

    try:
        is_running = (
            subprocess.check_output(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name]
            )
            .decode()
            .strip()
            == "true"
        )
    except subprocess.CalledProcessError:
        # Can't inspect container if it isn't running
        is_running = False

    if is_running:
        yield
        return

    out = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "-p",
            f"{conn_args['port']}:5432",
            "-d",
            "-e",
            f"POSTGRES_DB={conn_args['db']}",
            "-e",
            f"POSTGRES_PASSWORD={conn_args['pw']}",
            "-e",
            f"POSTGRES_USER={conn_args['user']}",
            "--health-cmd",
            "pg_isready",
            "--health-interval",
            "3s",
            "--health-timeout",
            "3s",
            "--health-retries",
            "15",
            image,
        ]
    )
    # Wait for postgres to become healthy
    for _ in range(10):
        out = subprocess.check_output(["docker", "inspect", container_name])
        inspect_info = json.loads(out)[0]
        health_status = inspect_info["State"]["Health"]["Status"]
        if health_status == "healthy":
            break
        else:
            time.sleep(1)
    else:
        raise Exception("Could not reach postgres comtainer. Check docker installation")
    yield
    # subprocess.call(["docker", "stop", container_name])
    return


@pytest.fixture(scope="function")
def clean_db(maybe_start_pg: None) -> Generator[str, None, None]:
    eng = create_engine(PYTEST_DB)
    with eng.begin() as connection:
        connection.execute(text("drop schema if exists vecs cascade;"))
    yield PYTEST_DB
    eng.dispose()


@pytest.fixture(scope="function")
def client(clean_db: str) -> Generator[vecs.Client, None, None]:
    client_ = vecs.create_client(clean_db)
    yield client_
