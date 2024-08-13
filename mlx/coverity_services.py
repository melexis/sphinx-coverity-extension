#!/usr/bin/python

"""Services and other utilities for Coverity scripting"""

# General
import csv
import logging
import re
from urllib.parse import urlencode
from sphinx.util.logging import getLogger

# For Coverity - REST API
import requests

# Coverity built in Impact statuses
IMPACT_LIST = {"High", "Medium", "Low"}

KIND_LIST = {"QUALITY", "SECURITY", "TEST"}

# Coverity built in Classifications
CLASSIFICATION_LIST = {
    "Unclassified",
    "Pending",
    "False Positive",
    "Intentional",
    "Bug",
    "Untested",
    "No Test Needed",
}

# Coverity built in Actions
ACTION_LIST = {
    "Undecided",
    "Fix Required",
    "Fix Submitted",
    "Modeling Required",
    "Ignore",
    "On hold",
    "For Interest Only",
}


class CoverityDefectService:
    """
    Coverity Defect Service (WebServices)
    """

    _version = "v2"

    def __init__(self, hostname):
        self._base_url = f"https://{hostname.strip('/')}"
        self._api_endpoint = f"https://{hostname.strip('/')}/api/{self.version}"
        self._checkers = []
        self._columns = []
        self.filters = ""

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
        url = self.api_endpoint.rstrip('/') + f"/streams/{stream}"
        self._request(url)

    def retrieve_issues(self, filters):
        """Retrieve issues from the server (Coverity Connect).

        Args:
            filters (json): The filters as json

        Returns:
            dict: The response
        """
        url = self.api_endpoint.rstrip('/') + \
            "/issues/search?includeColumnLabels=true&offset=0&queryType=bySnapshot&rowCount=-1&sortOrder=asc"
        return self._request(url, filters)

    def retrieve_column_keys(self):
        """Retrieves the column keys and associated display names.

        Returns:
            list[dict]: A list of dictionaries where the keys of each dictionary are 'columnKey' and 'name'
        """
        if not self._columns:
            url = f"{self.api_endpoint.rstrip('/')}/issues/columns?queryType=bySnapshot&retrieveGroupByColumns=false"
            self._columns = self._request(url)
        return self.columns

    def retrieve_checkers(self):
        """Retrieve the list of checkers from the server.

        Returns:
            list[str]: The list of valid checkers
        """
        if not self.checkers:
            url = f"{self.api_endpoint.rstrip('/')}/checkerAttributes/checker"
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
        logger = getLogger("coverity_logging")
        logger.warning(err_msg)
        return response.raise_for_status()

    @staticmethod
    def add_filter_rqt(name, req_csv, valid_list, allow_regex=False):
        """Add filter when the attribute is valid. If `valid_list` is not defined,
        all attributes of the CSV list are valid.
        The CSV list can allow regular expressions when `allow_regex` is set to True.

        Args:
            name (str): String representation of the attribute.
            req_csv (str): A CSV list of attribute values to query.
            valid_list (list/dict): The valid attributes.
            allow_regex (bool, optional): True when regular expressions are allowed. Defaults to False.

        Returns:
            str: The validated CSV list
            list[str]: The list of valid attributes
        """
        logging.info("Validate required %s [%s]", name, req_csv)
        validated = ""
        delim = ""
        filter_values = []
        for field in req_csv.split(","):
            if not valid_list or field in valid_list:
                logging.info("Classification [%s] is valid", field)
                filter_values.append(field)
                validated += delim + field
                delim = ","
            elif allow_regex:
                pattern = re.compile(field)
                for element in valid_list:
                    if pattern.search(element) and element not in filter_values:
                        filter_values.append(element)
                        validated += delim + element
                        delim = ","
            else:
                logging.error("Invalid %s filter: %s", name, field)
        return validated, filter_values

    def assemble_query_filter(self, column_key, filter_values, matcher_type):
        """Assemble a filter for a specific column

        Args:
            column_key (str): The column key
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
                assert column_key == "displayComponent"
            elif matcher_type == "idMatcher":
                matcher["id"] = filter_
            else:
                matcher["key"] = filter_
            matchers.append(matcher)
        return {
            "columnKey": column_key,
            "matchMode": "oneOrMoreMatch",
            "matchers": matchers
        }

    def get_defects(self, stream, filters, column_names):
        """Gets a list of defects for given stream, filters and column names.
        If a column name does not match the name of the `columns` property, the column can not be obtained because
        it need the correct corresponding column key.
        Column key `cid` is always obtained to use later in other functions.

        Args:
            stream (str): Name of the stream to query
            filters (dict): Dictionary with attribute names as keys and CSV lists of attribute values to query as values
            column_names (list[str]): The column names

        Returns:
            dict: The content of the request. This has a structure like:
                {
                    "offset": 0,
                    "totalRows": 2720,
                    "columns": [list of column keys]
                    "rows": list of [list of dictionaries {"key": <key>, "value": <value>}]
                }
        """
        logging.info("Querying Coverity for defects in stream [%s] ...", stream)
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
        # apply any filter on checker names
        if filters["checker"]:
            # this should be a keyMatcher (columnKey: checker)
            filter_values = self.handle_attribute_filter(filters["checker"], "Checker", self.checkers, allow_regex=True)
            if filter_values:
                query_filters.append(self.assemble_query_filter("checker", filter_values, "keyMatcher"))

        # apply any filter on impact status
        if filters["impact"]:
            # this should be a keyMatcher (columnKey: displayImpact)
            filter_values = self.handle_attribute_filter(filters["impact"], "Impact", IMPACT_LIST)
            if filter_values:
                query_filters.append(self.assemble_query_filter("displayImpact", filter_values, "keyMatcher"))

        # apply any filter on issue kind
        if filters["kind"]:
            # this should be a keyMatcher (columnKey: displayIssueKind)
            filter_values = self.handle_attribute_filter(filters["kind"], "displayIssueKind", KIND_LIST)
            if filter_values:
                query_filters.append(self.assemble_query_filter("displayIssueKind", filter_values, "keyMatcher"))

        # apply any filter on classification
        if filters["classification"]:
            # this should be a keyMatcher (columnKey: classification)
            filter_values = self.handle_attribute_filter(filters["classification"], "Classification", CLASSIFICATION_LIST)
            if filter_values:
                query_filters.append(self.assemble_query_filter("classification", filter_values, "keyMatcher"))

        # apply any filter on action
        if filters["action"]:
            # this should be a keyMatcher (columnKey: action)
            filter_values = self.handle_attribute_filter(filters["action"], "Action", ACTION_LIST)
            if filter_values:
                query_filters.append(self.assemble_query_filter("action", filter_values, "keyMatcher"))

        # apply any filter on Components
        if filters["component"]:
            # this should be a nameMatcher (columnKey: displayComponent)
            filter_values = self.handle_component_filter(filters["component"])
            if filter_values:
                query_filters.append(self.assemble_query_filter("displayComponent", filter_values, "nameMatcher"))

        # apply any filter on CWE values
        if filters["cwe"]:
            # this should be a idMatcher (columnKey: cwe)
            filter_values = self.handle_attribute_filter(filters["cwe"], "CWE", None)
            if filter_values:
                query_filters.append(self.assemble_query_filter("cwe", filter_values, "idMatcher"))

        # apply any filter on CID values
        if filters["cid"]:
            # this should be a idMatcher (columnKey: cid)
            filter_values = self.handle_attribute_filter(filters["cid"], "CID", None)
            if filter_values:
                query_filters.append(self.assemble_query_filter("cid", filter_values, "idMatcher"))
        column_names = [name.lower() for name in column_names]
        column_keys = set()
        for column in self.columns:
            if column["name"].lower() in column_names:
                column_keys.add(column["columnKey"])
        if "location" in column_names:
            column_keys.add("lineNumber")
            column_keys.add("displayFile")
        if "comment" in column_names:
            column_keys.add("lastTriageComment")
        if "reference" in column_names:
            column_keys.add("externalReference")
        column_keys.add("cid")
        data = {
            "filters": query_filters,
            "columns": list(column_keys),
            "snapshotScope": {
                "show": {
                    "scope": "last()",
                    "includeOutdatedSnapshots": False
                },
                "compareTo": {
                    "scope": "last()",
                    "includeOutdatedSnapshots": False
                }
            }
        }
        logging.info("Running Coverity query...")
        return self.retrieve_issues(data)

    def handle_attribute_filter(self, attribute_values, name, *args, **kwargs):
        """Applies any filter on an attribute's values.

        Args:
            attribute_values (str): A CSV list of attribute values to query.
            name (str): String representation of the attribute.

        Returns:
            list[str]: The list of valid attributes
        """
        logging.info("Using %s filter [%s]", name, attribute_values)
        validated, filter_values = self.add_filter_rqt(name, attribute_values, *args, **kwargs)
        logging.info("Resolves to [%s]", validated)
        if validated:
            self.filters += "<%s(%s)> " % (name, validated)
        return filter_values

    def handle_component_filter(self, attribute_values):
        """Applies any filter on the component attribute's values.

        Args:
            attribute_values (str): A CSV list of attribute values to query.

        Returns:
            list[str]: The list of attributes
        """
        logging.info("Using Component filter [%s]", attribute_values)
        parser = csv.reader([attribute_values])
        filter_values = []
        for fields in parser:
            for _, field in enumerate(fields):
                field = field.strip()
                filter_values.append(field)
        self.filters += "<Components(%s)> " % (attribute_values)
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
        params = {'stream': stream, 'cid': cid}
        return f"{self.base_url}/query/defects.htm?" + urlencode(params)


if __name__ == "__main__":
    print("Sorry, no main here")
