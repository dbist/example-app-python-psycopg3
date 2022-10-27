# example-app-python-psycopg3

This repo has a simple CRUD Python application that uses the [`psycopg3`](https://www.psycopg.org/psycopg3/docs/) driver to talk to a CockroachDB cluster using short-lived tokens.

For details on creating a CockroachDB cluster and running the code, see [this tutorial](https://www.cockroachlabs.com/docs/stable/build-a-python-app-with-cockroachdb-psycopg3.html).

## Before you begin

To run this example you must have:

- Python 3
- `pip` version 20.3 or greater

## Install the dependencies

In a terminal run the following command:

~~~ shell
pip install -r requirements.txt
~~~

## Set the CockroachDB jwt SSO requirements for Okta

## Set the following environment variables

In a terminal set the following environment variables.

For example on Mac and Linux:
~~~ shell
export OKTAURL=https://dev-number.okta.com/oauth2/v1/token
export CLIENT_ID=<okta-client-id>
export CLIENT_SECRET=<okta-client-secret>
export OKTAUSERNAME=<Okta user>
export OKTAPASSWORD=<Okta password>
~~~

For detailed steps on creating a CockroachDB cluster, see the [tutorial](https://www.cockroachlabs.com/docs/stable/build-a-python-app-with-cockroachdb-psycopg3.html).

## Run the example

To run the example, in a terminal run the following command:

~~~ shell
python3 example.py
~~~