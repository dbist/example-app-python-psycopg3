#!/usr/bin/env python3
"""
Test psycopg with CockroachDB.
"""

import logging
import os
import random
import time
import uuid
import requests
import json
from argparse import ArgumentParser, RawTextHelpFormatter

import psycopg
from psycopg.errors import SerializationFailure, Error
from psycopg.rows import namedtuple_row


def create_accounts(conn):
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS accounts (id UUID PRIMARY KEY, balance INT)"
        )
        cur.execute(
            "UPSERT INTO accounts (id, balance) VALUES (%s, 1000), (%s, 250)", (id1, id2))
        logging.debug("create_accounts(): status message: %s",
                      cur.statusmessage)
    return [id1, id2]


def delete_accounts(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM accounts")
        logging.debug("delete_accounts(): status message: %s",
                      cur.statusmessage)


def print_balances(conn):
    with conn.cursor() as cur:
        print(f"Balances at {time.asctime()}:")
        for row in cur.execute("SELECT id, balance FROM accounts"):
            print("account id: {0}  balance: ${1:2d}".format(row.id, row.balance))


def transfer_funds(conn, frm, to, amount):
    with conn.cursor() as cur:

        # Check the current balance.
        cur.execute("SELECT balance FROM accounts WHERE id = %s", (frm,))
        from_balance = cur.fetchone()[0]
        if from_balance < amount:
            raise RuntimeError(
                f"insufficient funds in {frm}: have {from_balance}, need {amount}"
            )

        # Perform the transfer.
        cur.execute(
            "UPDATE accounts SET balance = balance - %s WHERE id = %s", (
                amount, frm)
        )
        cur.execute(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s", (
                amount, to)
        )

    logging.debug("transfer_funds(): status message: %s", cur.statusmessage)


def run_transaction(conn, op, max_retries=3):
    """
    Execute the operation *op(conn)* retrying serialization failure.

    If the database returns an error asking to retry the transaction, retry it
    *max_retries* times before giving up (and propagate it).
    """
    # leaving this block the transaction will commit or rollback
    # (if leaving with an exception)
    with conn.transaction():
        for retry in range(1, max_retries + 1):
            try:
                op(conn)

                # If we reach this point, we were able to commit, so we break
                # from the retry loop.
                return

            except SerializationFailure as e:
                # This is a retry error, so we roll back the current
                # transaction and sleep for a bit before retrying. The
                # sleep time increases for each failed transaction.
                logging.debug("got error: %s", e)
                conn.rollback()
                logging.debug("EXECUTE SERIALIZATION_FAILURE BRANCH")
                sleep_seconds = (2**retry) * 0.1 * (random.random() + 0.5)
                logging.debug("Sleeping %s seconds", sleep_seconds)
                time.sleep(sleep_seconds)

            except psycopg.Error as e:
                logging.debug("got error: %s", e)
                logging.debug("EXECUTE NON-SERIALIZATION_FAILURE BRANCH")
                raise e

        raise ValueError(
            f"transaction did not succeed after {max_retries} retries")


def main():
    opt = parse_cmdline()
    logging.basicConfig(level=logging.DEBUG if opt.verbose else logging.INFO)
    try:
        # Attempt to connect to cluster with connection string provided to
        # script. By default, this script uses the value saved to the
        # DATABASE_URL environment variable.
        # For information on supported connection string formats, see
        # https://www.cockroachlabs.com/docs/stable/connect-to-the-database.html.

        client_id = opt.client_id
        client_secret = opt.client_secret
        username = opt.username
        password = opt.password
        url = opt.url

        headers = {'Content-Type': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
        data='grant_type=password&username=' + username + '&password=' + password + '&scope=openid offline_access'

        # capture the id_token and use it in the psycopg connection, we must include the options flag
        json_response = get_id_token(url, data, headers, client_id, client_secret)
        id_token = json_response["id_token"]
        refresh_token = json_response["refresh_token"]

        print()
        print("Initiate authentication with a new id_token:")
        execute_workload(id_token)

        data = "grant_type=refresh_token&scope=openid offline_access&refresh_token=" + refresh_token

        json_refresh_response = get_id_token(url, data, headers, client_id, client_secret)
        new_id_token = json_refresh_response["id_token"]

        print()
        print("Initiate authentication with a refreshed id_token:")
        execute_workload(new_id_token)

        print()
        print("Initiate authentication with a bogus id_token:")
        execute_workload("bogus")

    except Exception as e:
        logging.fatal("database connection failed")
        logging.fatal(e)
        return

def execute_workload(id_token):
    with psycopg.connect("host=lb dbname=defaultdb user=roach password={} port=26257 sslmode=verify-full sslrootcert=/certs/ca.crt options=--crdb:jwt_auth_enabled=true".format(id_token),
                               application_name="$ using_jwt_token_psycopg3",
                               row_factory=namedtuple_row) as conn:

        ids = create_accounts(conn)
        print_balances(conn)

        amount = 100
        toId = ids.pop()
        fromId = ids.pop()

        try:
            run_transaction(conn, lambda conn: transfer_funds(conn, fromId, toId, amount))
        except ValueError as ve:
            # Below, we print the error and continue on so this example is easy to
            # run (and run, and run...).  In real code you should handle this error
            # and any others thrown by the database interaction.
                logging.debug("run_transaction(conn, op) failed: %s", ve)
                pass
        except psycopg.Error as e:
                logging.debug("got error: %s", e)
                raise e

        print_balances(conn)

        delete_accounts(conn)


def get_id_token(url, data, headers, client_id, client_secret):
    r = requests.post(url, data, headers=headers, auth=(client_id, client_secret))
    return json.loads(r.text)


def parse_cmdline():
    parser = ArgumentParser(description=__doc__,
                            formatter_class=RawTextHelpFormatter)

    parser.add_argument("-v", "--verbose",
                        action="store_true", help="print debug info")

    parser.add_argument(
        "url",
        default=os.environ.get("OKTAURL"),
        nargs="?",
        help="""\
Okta URL\
 (default: value of the OKTALURL environment variable)
            """,
    )

    parser.add_argument(
        "client_id",
        default=os.environ.get("CLIENT_ID"),
        nargs="?",
        help="""\
Okta Client ID\
 (default: value of the CLIENT_ID environment variable)
            """,
    )

    parser.add_argument(
        "client_secret",
        default=os.environ.get("CLIENT_SECRET"),
        nargs="?",
        help="""\
Okta Client Secret\
 (default: value of the SECRET environment variable)
            """,
    )

    parser.add_argument(
        "username",
        default=os.environ.get("OKTAUSERNAME"),
        nargs="?",
        help="""\
Okta Username\
 (default: value of the OKTAUSERNAME environment variable)
            """,
    )

    parser.add_argument(
        "password",
        default=os.environ.get("OKTAPASSWORD"),
        nargs="?",
        help="""\
Okta Password\
 (default: value of the OKTAPASSWORD environment variable)
            """,
    )

    opt = parser.parse_args()
    if opt.client_id is None:
        parser.error("Okta Client ID is not set")
    elif opt.client_secret is None:
        parser.error("Okta Client Secret is not set")
    elif opt.username is None:
        parser.error("Okta Username is not set")
    elif opt.password is None:
        parser.error("Okta Password is not set")
    elif opt.url is None:
        parser.error("Okta Url is not set")
    return opt


if __name__ == "__main__":
    main()

