#!/usr/bin/python

"""Services and other utilities for Coverity scripting"""

import csv
import re
from collections import namedtuple
from urllib.parse import urlencode
import requests
from sphinx.util.logging import getLogger

from mlx.coverity import report_info, report_warning

# Coverity built in Impact statuses
IMPACT_LIST = ["High", "Medium", "Low"]

KIND_LIST = ["QUALITY", "SECURITY", "TEST"]

# Coverity built in Classifications
CLASSIFICATION_LIST = [
    "Unclassified",
    "Pending",
    "False Positive",
    "Intentional",
    "Bug",
    "Untested",
    "No Test Needed",
]

# Coverity built in Actions
ACTION_LIST = [
    "Undecided",
    "Fix Required",
    "Fix Submitted",
    "Modeling Required",
    "Ignore",
    "On hold",
    "For Interest Only",
]


class CoverityDefectService:
    """
    Convenience class for retrieving data from the Coverity REST API
    """

    _version = "v2"

    def __init__(self, hostname):
        hostname = hostname.strip('/')
        self._base_url = f"https://{hostname}"
        self._api_endpoint = f"https://{hostname}/api/{self.version}"
        self._checkers = []
        self._columns = {}
        self.logger = getLogger("mlx.coverity_logging")

    @property
    def base_url(self):
        """str: The base URL of the service."""
        return self._base_url

    @property
    def api_endpoint(self):
        """str: The API endpoint of the service."""
        return self._api_endpoint

    @property
    def version(self):
        """str: The API version"""
        return self._version

    @property
    def checkers(self):
        """list[str]: All valid checkers available"""
        return self._checkers

    @property
    def columns(self):
        """list[dict]: A list of dictionaries where the keys of each dictionary:
        - columnKey: The key of the column
        - name: The name of the column
        """
        return self._columns

    def column_keys(self, column_names):
        """The column keys corresponding to the given column names in the `col` option

        Args:
            column_names (list[str]): The column names given by the `col` option
        """
        special_columns = {
            "location": {"lineNumber", "displayFile"},
            "comment": {"lastTriageComment"},
            "reference": {"externalReference"}
        }
        column_keys = {"cid"}

        for column_name in column_names:
            column_name_lower = column_name.lower()
            if column_name_lower in special_columns:
                column_keys.update(special_columns[column_name_lower])
            elif column_name_lower in self.columns:
                column_keys.add(self.columns[column_name_lower])
            else:
                self.logger.warning(f"Invalid column name {column_name!r}")
        return column_keys

    def login(self, username, password):
        """Authenticate a session using the given username and password .

        Args:
            username (str): Username to log in
            password (str): Password to log in
        """
        self.session = requests.Session()
        self.session.auth = (username, password)

    def validate_stream(self, stream):
        """Validate stream by retrieving the specified stream.
        When the request fails, the stream does not exist or the user does not have acces to it.

        Args:
            stream (str): The stream name
        """
        url = f"{self.api_endpoint}/streams/{stream}"
        self._request(url)

    def validate_snapshot(self, snapshot):
        """Validate snapshot by retrieving the specified snapshot.
        When the request fails, the snapshot does not exist or the user does not have acces to it.
        In this case a warning is logged and continues with the latest snapshot.

        Args:
            snapshot (str): The snapshot ID
        """
        url = f"{self.api_endpoint}/snapshots/{snapshot}"
        response = self.session.get(url)
        if response.ok:
            report_info(f"Snapshot ID {snapshot} is valid")
            valid_snapshot = snapshot
        else:
            report_warning(f"No snapshot found for ID {snapshot}; Continue with using the latest snapshot.", "")
            valid_snapshot = "last()"

        return valid_snapshot

    def retrieve_issues(self, filters):
        """Retrieve issues from the server (Coverity Connect).

        Args:
            filters (dict): The filters for the query

        Returns:
            dict: The response
        """
        params = {
            "includeColumnLabels": "true",
            "offset": 0,
            "queryType": "bySnapshot",
            "rowCount": -1,
            "sortOrder": "asc",
        }
        url = f"{self.api_endpoint}/issues/search?{urlencode(params)}"
        return self._request(url, filters)

    def retrieve_column_keys(self):
        """Retrieves the column keys and associated display names.

        Returns:
            dict: All available column names with respective column keys.
        """
        if not self._columns:
            params = {
                "queryType": "bySnapshot",
                "retrieveGroupByColumns": "false"
            }
            url = f"{self.api_endpoint}/issues/columns?{urlencode(params)}"
            columns = self._request(url)
            if columns:
                self._columns = requests.structures.CaseInsensitiveDict(
                    ((column["name"], column["columnKey"]) for column in columns)
                )
        return self.columns

    def retrieve_checkers(self):
        """Retrieve the list of checkers from the server.

        Returns:
            list[str]: The list of valid checkers
        """
        if not self.checkers:
            url = f"{self.api_endpoint}/checkerAttributes/checker"
            checkers = self._request(url)
            if checkers and "checkerAttributedata" in checkers:
                self._checkers = [checker["key"] for checker in checkers["checkerAttributedata"]]
        return self.checkers

    def _request(self, url, data=None):
        """Perform a POST or GET request to the specified url.
        Uses a GET request when data is `None`, uses a POST request otherwise

        Args:
            url (str): The URL for the request
            data (dict): Optional data to send

        Returns:
            dict: the content of server's response

        Raises:
            requests.HTTPError
        """
        if data:
            response = self.session.post(url, json=data)
        else:
            response = self.session.get(url)
        if response.ok:
            return response.json()
        try:
            err_msg = response.json()["message"]
        except (requests.exceptions.JSONDecodeError, KeyError):
            err_msg = response.content.decode()
        self.logger.error(err_msg)
        return response.raise_for_status()

    def assemble_query_filter(self, column_name, filter_values, matcher_type):
        """Assemble a filter for a specific column

        Args:
            column_name (str): The column name in lowercase
            filter_values (list[str]): The list of valid values to filter on
            matcher_type (str): The type of the matcher (nameMatcher, idMatcher or keyMatcher)

        Returns:
            dict: New filter for API queries
        """
        matchers = []
        for filter_ in filter_values:
            matcher = {"type": matcher_type}
            if matcher_type == "nameMatcher":
                matcher["name"] = filter_
                matcher["class"] = "Component"
                assert column_name == "component"
            elif matcher_type == "idMatcher":
                matcher["id"] = filter_
            else:
                matcher["key"] = filter_
            matchers.append(matcher)

        if column_name not in self.columns:
            self.logger.warning(f"Invalid column name {column_name!r}; Retrieve column keys first.")

        return {
            "columnKey": self.columns[column_name],
            "matchMode": "oneOrMoreMatch",
            "matchers": matchers
        }

    def get_defects(self, stream, filters, column_names, snapshot):
        """Gets a list of defects for the given stream, filters and column names.

        If no snapshot ID is given, the last snapshot is taken.
        If a column name does not match the name of the `columns` property, the column can not be obtained because
        it need the correct corresponding column key.
        Column key `cid` is always obtained to use later in other functions.

        Args:
            stream (str): Name of the stream to query
            filters (dict): Dictionary with attribute names as keys and CSV lists of attribute values to query as values
            column_names (list[str]): The column names
            snapshot (str): The snapshot ID; If empty the last snapshot is taken.

        Returns:
            dict: The content of the request. This has a structure like:
                {
                    "offset": 0,
                    "totalRows": 2720,
                    "columns": [list of column keys]
                    "rows": list of [list of dictionaries {"key": <key>, "value": <value>}]
                }
        """
        report_info(f"Querying Coverity for defects in stream [{stream}] ...")
        query_filters = [
            {
                "columnKey": "streams",
                "matchMode": "oneOrMoreMatch",
                "matchers": [
                    {
                        "class": "Stream",
                        "name": stream,
                        "type": "nameMatcher"
                    }
                ]
            }
        ]

        Filter = namedtuple("Filter", "name matcher_type values allow_regex", defaults=[[], False])
        filter_options = {
            "checker": Filter("Checker", "keyMatcher", self.checkers, True),
            "impact": Filter("Impact", "keyMatcher", IMPACT_LIST),
            "kind": Filter("Issue Kind", "keyMatcher", KIND_LIST),
            "classification": Filter("Classification", "keyMatcher", CLASSIFICATION_LIST),
            "action": Filter("Action", "keyMatcher", ACTION_LIST),
            "cwe": Filter("CWE", "idMatcher"),
            "cid": Filter("CID", "idMatcher")
        }

        for option, filter in filter_options.items():
            if (filter_option := filters[option]) and (filter_values := self.handle_attribute_filter(
                    filter_option, filter.name, filter.values, filter.allow_regex)):
                if filter_values:
                    query_filters.append(self.assemble_query_filter(filter.name, filter_values, filter.matcher_type))

        if (filter := filters["component"]) and (filter_values := self.handle_component_filter(filter)):
            query_filters.append(self.assemble_query_filter("Component", filter_values, "nameMatcher"))

        data = {
            "filters": query_filters,
            "columns": list(self.column_keys(column_names)),
            "snapshotScope": {
                "show": {
                    "scope": snapshot,
                    "includeOutdatedSnapshots": False
                }
            }
        }

        defects_data = self.retrieve_issues(data)
        report_info("done")

        return defects_data

    def handle_attribute_filter(self, attribute_values, name, valid_attributes, allow_regex=False):
        """Process the given CSV list of attribute values by filtering out the invalid ones while logging an error.
        The CSV list can allow regular expressions when `allow_regex` is set to True.

        Args:
            attribute_values (str): A CSV list of attribute values to query.
            name (str): String representation of the attribute.
            valid_attributes (list/dict): All valid/possible attribute values.
            allow_regex (bool): True to treat filter values as regular expressions, False to require exact matches

        Returns:
            set[str]: The attributes values to query with
        """
        report_info(f"Using {name!r} filter [{attribute_values}]")
        filter_values = set()
        for field in attribute_values.split(","):
            if not valid_attributes or field in valid_attributes:
                report_info(f"Classification [{field}] is valid")
                filter_values.add(field)
            elif allow_regex:
                pattern = re.compile(field)
                for element in valid_attributes:
                    if pattern.search(element):
                        filter_values.add(element)
            else:
                self.logger.error(f"Invalid {name} filter: {field}")
        return filter_values

    def handle_component_filter(self, attribute_values):
        """Applies any filter on the component attribute's values.

        Args:
            attribute_values (str): A CSV list of attribute values to query.

        Returns:
            list[str]: The list of attributes
        """
        report_info(f"Using 'Component' filter [{attribute_values}]")
        parser = csv.reader([attribute_values])
        filter_values = []
        for fields in parser:
            for _, field in enumerate(fields):
                field = field.strip()
                filter_values.append(field)
        return filter_values

    def defect_url(self, stream, cid):
        """Get URL for given defect CID
        https://machine1.eng.company.com/query/defects.htm?stream=StreamA&cid=1234

        Args:
            stream (str): The name of the stream
            cid (int): The CID of the given defect

        Returns:
            str: The URL to the requested defect
        """
        params = {
            'stream': stream,
            'cid': cid
        }
        return f"{self.base_url}/query/defects.htm?{urlencode(params)}"


if __name__ == "__main__":
    print("Sorry, no main here")
