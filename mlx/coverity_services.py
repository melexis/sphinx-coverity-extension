#!/usr/bin/python

"""Services and other utilities for Coverity scripting"""

# General
import csv
import json
import logging
import re
from sphinx.util.logging import getLogger

# For Coverity - REST API
import requests

from mlx.coverity_logging import report_info

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
        self._hostname = hostname
        self.base_url = f"https://{hostname.strip('/')}/api/{self.version}"
        self._checkers = []
        self._columns = []
        self.filters = ""

    @property
    def hostname(self):
        """str: The hostname"""
        return self._hostname

    @property
    def base_url(self):
        """str: The base URL of the service."""
        return self._base_url

    @base_url.setter
    def base_url(self, value):
        if not re.fullmatch(r"https://.+/api/v\d+/?", value):
            raise ValueError(
                f"Invalid base URL. Expected 'http(s)://<hostname>/api/{self.version}(/)'; Got {value}"
            )
        self._base_url = value

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
        url = self.base_url.rstrip('/') + f"/streams/{stream}"
        self._get_request(url)

    def retrieve_issues(self, filters):
        """Retrieve issues from the server (Coverity Connect).

        Args:
            filters (json): The filters as json

        Returns:
            dict: The response
        """
        url = self.base_url.rstrip('/') + \
            "/issues/search?includeColumnLabels=true&offset=0&queryType=bySnapshot&rowCount=-1&sortOrder=asc"
        return self._post_request(url, filters)

    def retrieve_column_keys(self):
        """Retrieves the column keys and associated display names.

        Returns:
            list[dict]: A list of dictionaries where the keys of each dictionary are 'columnKey' and 'name'
        """
        if not self._columns:
            url = f"{self.base_url.rstrip('/')}/issues/columns?queryType=bySnapshot&retrieveGroupByColumns=false"
            self._columns = self._get_request(url)
        return self.columns

    def retrieve_checkers(self):
        """Retrieve the list of checkers from the server.

        Returns:
            list[str]: The list of valid checkers
        """
        if not self.checkers:
            url = f"{self.base_url.rstrip('/')}/checkerAttributes/checker"
            checkers = self._get_request(url)
            if checkers and "checkerAttributedata" in checkers:
                self._checkers = [checker["key"] for checker in checkers["checkerAttributedata"]]
        return self.checkers

    def _get_request(self, url):
        """Make a GET request to the API.

        Args:
            url (str): The url to request data via GET request

        Returns:
            dict: the content of server's response

        Raises:
            requests.HTTPError
        """
        req = self.session.get(url)
        if req.ok:
            return json.loads(req.content)
        else:
            try:
                message = json.loads(req.content)["message"]
            except:
                message = req.content.decode()
            logger = getLogger("coverity_logging")
            logger.warning(message)
            return req.raise_for_status()

    def _post_request(self, url, data):
        """Perform a POST request to the specified url.

        Args:
            url (str): The url to request data via POST request
            data (dict): The data to send

        Returns:
            dict: the content of server's response

        Raises:
            requests.HTTPError
        """
        req = self.session.post(url, json=data)
        if req.ok:
            return json.loads(req.content)
        else:
            try:
                message = json.loads(req.content)["message"]
            except:
                message = req.content.decode()
            logger = getLogger("coverity_logging")
            logger.warning(message)
            return req.raise_for_status()

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
        filter_list = []
        for field in req_csv.split(","):
            if not valid_list or field in valid_list:
                logging.info("Classification [%s] is valid", field)
                filter_list.append(field)
                validated += delim + field
                delim = ","
            elif allow_regex:
                pattern = re.compile(field)
                for element in valid_list:
                    if pattern.search(element) and element not in filter_list:
                        filter_list.append(element)
                        validated += delim + element
                        delim = ","
            else:
                logging.error("Invalid %s filter: %s", name, field)
        return validated, filter_list

    def add_new_filters(self, request_filters, column_key, filter_list, matcher_type, matcher_class=None):
        """Add new filter to the filters list of the JSON request data

        Args:
            request_filters (list[dict]): The list of all filters of the JSON request data
            column_key (str): The column key
            filter_list (list[str]): The list of validated filters
            matcher_type (str): The type of matcher (nameMatcher, idMatcher or keyMatcher)
            matcher_class (str): The name of the column key which represents the class
        """
        matchers = []
        # dateMatcher also exist but due to hardcoded way of working, this is skipped
        if matcher_type == "nameMatcher":
            for filter in filter_list:
                matchers.append({
                    "class": matcher_class,
                    "name": filter,
                    "type": "nameMatcher",
                })
            request_filters.append({
                "columnKey": column_key,
                "matchMode": "oneOrMoreMatch",
                "matchers": matchers
            })
        elif matcher_type == "idMatcher":
            for filter in filter_list:
                matchers.append({
                    "id": filter,
                    "type": "idMatcher"
                })
            request_filters.append({
                "columnKey": column_key,
                "matchMode": "oneOrMoreMatch",
                "matchers": matchers
            })
        else:
            for filter in filter_list:
                matchers.append({
                    "key": filter,
                    "type": "keyMatcher"
                })
            request_filters.append(
                {
                    "columnKey": column_key,
                    "matchMode": "oneOrMoreMatch",
                    "matchers": matchers
                }
            )

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
        request_filters = [
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
            filter_list = self.handle_attribute_filter(filters["checker"], "Checker", self.checkers, allow_regex=True)
            if filter_list:
                self.add_new_filters(request_filters, "checker", filter_list, "keyMatcher")

        # apply any filter on impact status
        if filters["impact"]:
            # this should be a keyMatcher (columnKey: displayImpact)
            filter_list = self.handle_attribute_filter(filters["impact"], "Impact", IMPACT_LIST)
            if filter_list:
                self.add_new_filters(request_filters, "displayImpact", filter_list, "keyMatcher")

        # apply any filter on issue kind
        if filters["kind"]:
            # this should be a keyMatcher (columnKey: displayIssueKind)
            filter_list = self.handle_attribute_filter(filters["kind"], "displayIssueKind", KIND_LIST)
            if filter_list:
                self.add_new_filters(request_filters, "displayIssueKind", filter_list, "keyMatcher")

        # apply any filter on classification
        if filters["classification"]:
            # this should be a keyMatcher (columnKey: classification)
            filter_list = self.handle_attribute_filter(
                filters["classification"],
                "Classification",
                CLASSIFICATION_LIST,
            )
            if filter_list:
                self.add_new_filters(request_filters, "classification", filter_list, "keyMatcher")

        # apply any filter on action
        if filters["action"]:
            # this should be a keyMatcher (columnKey: action)
            filter_list = self.handle_attribute_filter(filters["action"], "Action", ACTION_LIST)
            if filter_list:
                self.add_new_filters(request_filters, "action", filter_list, "keyMatcher")

        # apply any filter on Components
        if filters["component"]:
            # this should be a nameMatcher (columnKey: displayComponent)
            filter_list = self.handle_component_filter(filters["component"])
            if filter_list:
                self.add_new_filters(
                    request_filters,
                    "displayComponent",
                    filter_list,
                    "nameMatcher",
                    "Component",
                )

        # apply any filter on CWE values
        if filters["cwe"]:
            # this should be a idMatcher (columnKey: cwe)
            filter_list = self.handle_attribute_filter(filters["cwe"], "CWE", None)
            if filter_list:
                self.add_new_filters(request_filters, "cwe", filter_list, "idMatcher")

        # apply any filter on CID values
        if filters["cid"]:
            # this should be a idMatcher (columnKey: cid)
            filter_list = self.handle_attribute_filter(filters["cid"], "CID", None)
            if filter_list:
                self.add_new_filters(request_filters, "cid", filter_list, "idMatcher")
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
            "filters": request_filters,
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
        validated, filter_list = self.add_filter_rqt(name, attribute_values, *args, **kwargs)
        logging.info("Resolves to [%s]", validated)
        if validated:
            self.filters += "<%s(%s)> " % (name, validated)
        return filter_list

    def handle_component_filter(self, attribute_values):
        """Applies any filter on the component attribute's values.

        Args:
            attribute_values (str): A CSV list of attribute values to query.

        Returns:
            list[str]: The list of attributes
        """
        logging.info("Using Component filter [%s]", attribute_values)
        parser = csv.reader([attribute_values])
        filter_list = []
        for fields in parser:
            for _, field in enumerate(fields):
                field = field.strip()
                filter_list.append(field)
        self.filters += "<Components(%s)> " % (attribute_values)
        return filter_list

    def defect_url(self, stream, cid):
        """Get URL for given defect CID
        https://machine1.eng.company.com/query/defects.htm?stream=StreamA&cid=1234

        Args:
            stream (str): The name of the stream
            cid (int): The cid of the given defect

        Returns:
            str: The url to the defect with given CID
        """
        return f"https://{self.hostname.strip('/')}/query/defects.htm?stream={stream}&cid={cid}"


if __name__ == "__main__":
    print("Sorry, no main here")
