from typing import Any, Dict, Optional

from flask_appbuilder.fieldwidgets import BS3TextFieldWidget
from flask_babel import lazy_gettext
from TM1py.Services import TM1Service
from wtforms import StringField

from airflow.exceptions import AirflowException
from airflow.hooks.base import BaseHook


class TM1Hook(BaseHook):
    """
    Hook for TM1 Rest API

    Args:
        tm1_conn_id (str):  The name of the Airflow connection
        with connection information for the TM1 API
    """

    default_conn_name: str = "tm1_default"
    conn_type: str = "tm1"
    conn_name_attr: str = "tm1_conn_id"
    hook_name: str = "TM1"

    def __init__(
        self,
        tm1_conn_id: str = default_conn_name,
    ):

        self.tm1_conn_id = tm1_conn_id

        # getch this with get_conn
        self.client: Optional[TM1Service] = None
        self.server_name: Optional[str] = None
        self.server_version: Optional[str] = None

        # is there a use case without a connection in place?
        conn = self.get_connection(tm1_conn_id)

        extra = conn.extra_dejson
        self.user: str = conn.login
        self.password: str = conn.get_password()
        self.namespace: str = conn.schema

        # is this the best way to acccess the connection?
        # or should I use helper methods instead?
        self.address: str = conn.host
        self.port: str = str(conn.port)

        # it might nice to be able to initialise and use the hook without
        # authenticating in order to ping a public endpoint to see if it's down
        # I think this will die if these aren't provided (or will it just given empty strings)
        self.user = conn.login
        self.password = conn.get_password()

        # get relevant extra params
        self.ssl: bool = extra.get("ssl", "False") == "True"
        self.session_context = "Airflow"

    def get_conn(self) -> TM1Service:
        """Function that creates a new TM1py Service object and returns it"""

        if not self.client:
            self.log.debug("Creating tm1 client for conn_id: %s", self.tm1_conn_id)

            if not self.tm1_conn_id:
                raise AirflowException("Failed to create tm1 client. No tm1_conn_id provided")

            try:
                #todo: compatible with bsae url
                # when port is None, self.address should be the base_url parameter in TM1Service
                if self.port == '':
                    self.client = TM1Service(
                        address=self.address,
                        user=self.user,
                        password="" if self.password is None else self.password,
                        ssl=self.ssl,
                        namespace=self.namespace,
                        session_context=self.session_context,
                    )
                else: 
                    self.client = TM1Service(
                        # basic example
                        address=self.address,
                        port=self.port,
                        user=self.user,
                        password="" if self.password is None else self.password,
                        ssl=self.ssl,
                        namespace=self.namespace,
                        session_context=self.session_context,
                    )
                self.server_name = self.client.server.get_server_name()
                self.server_version = self.client.server.get_product_version()

            except ValueError as tm1_error:
                raise AirflowException(f"Failed to create tm1 client, tm1 error: {str(tm1_error)}")
            except Exception as e:
                raise AirflowException(f"Failed to create tm1 client, error: {str(e)}")

        return self.client

    def test_connection(self):
        status, message = False, ""
        try:
            tm1 = self.get_conn()
            status = tm1.connection.is_connected()
            message = "Connection successfully tested"
        except Exception as e:
            status = False
            message = str(e)

        return status, message

    def logout(self):
        self.tm1.logout()

    def get_no_auth_url(self):
        """Return a URL based on the host and port"""

        # how to handle http vs https and how does this relate to the ssl param?
        no_auth_url = f"http://{self.address}:{self.port}/api/v1/$metadata"

        return no_auth_url

    @staticmethod
    def get_connection_form_widgets() -> Dict[str, Any]:
        return {
            "ssl": StringField(
                lazy_gettext("SSL"),
                widget=BS3TextFieldWidget(),
                description=lazy_gettext("True or False"),
            ),
        }

    @classmethod
    def get_ui_field_behaviour(cls) -> Dict[str, Any]:
        return {
            "hidden_fields": [
                "extra",
            ],
            "relabeling": {
                "host": "Address",
                "schema": "Namespace",
                "login": "User",
            },
        }
