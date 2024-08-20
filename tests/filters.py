# filters, columns_names, response data in apart python bestand

from collections import namedtuple

Filter = namedtuple("Filter", "filters column_names request_data")

# Test with no filters and no column names
test_defect_filter_0 = Filter(
    {
        "checker": None,
        "impact": None,
        "kind": None,
        "classification": None,
        "action": None,
        "component": None,
        "cwe": None,
        "cid": None,
    },
    [],
    {
        "filters": [
            {
                "columnKey": "streams",
                "matchMode": "oneOrMoreMatch",
                "matchers": [{"class": "Stream", "name": "test_stream", "type": "nameMatcher"}]
            }
        ],
        "columns": ["cid"],
        "snapshotScope": {
            "show": {"scope": "last()", "includeOutdatedSnapshots": False},
            "compareTo": {"scope": "last()", "includeOutdatedSnapshots": False}
        }
    }
)

test_defect_filter_1 = Filter(
    {
        "checker": "MISRA",
        "impact": None,
        "kind": None,
        "classification": "Intentional,Bug,Pending,Unclassified",
        "action": None,
        "component": None,
        "cwe": None,
        "cid": None,
    },
    ["CID", "Classification", "Checker", "Comment"],
    {"filters": [
        {"columnKey": "streams", "matchMode": "oneOrMoreMatch", "matchers": [
                {"class": "Stream", "name": "test_stream", "type": "nameMatcher"}
            ]
        },
        {"columnKey": "checker", "matchMode": "oneOrMoreMatch", "matchers": [
                {"type": "keyMatcher", "key": "MISRA 2"},
                {"type": "keyMatcher", "key": "MISRA 1"},
                {"type": "keyMatcher", "key": "MISRA 3"}
            ]
        },
        {"columnKey": "classification", "matchMode": "oneOrMoreMatch", "matchers": [
                {"type": "keyMatcher", "key": "Bug"},
                {"type": "keyMatcher", "key": "Pending"},
                {"type": "keyMatcher", "key": "Unclassified"},
                {"type": "keyMatcher", "key": "Intentional"}
            ]
        }
    ],
    "columns": ["cid", "checker", "lastTriageComment", "classification"],
    "snapshotScope": {
        "show": {"scope": "last()", "includeOutdatedSnapshots": False},
        "compareTo": {"scope": "last()", "includeOutdatedSnapshots": False}
    }}
)

test_defect_filter_2 = Filter(
    {
        "checker": None,
        "impact": None,
        "kind": None,
        "classification": None,
        "action": None,
        "component": None,
        "cwe": None,
        "cid": None,
    },
    ["CID", "Checker", "Status", "Comment"],
    {'filters': [
        {'columnKey': 'streams', 'matchMode': 'oneOrMoreMatch', 'matchers': [
            {'class': 'Stream', 'name': 'test_stream', 'type': 'nameMatcher'}
            ]
        }],
     'columns': ['status', 'cid', 'checker', 'lastTriageComment'],
     'snapshotScope': {
        'show': {'scope': 'last()', 'includeOutdatedSnapshots': False},
        'compareTo': {'scope': 'last()', 'includeOutdatedSnapshots': False}
    }}
)

test_defect_filter_3 = Filter(
    {
        "checker": None,
        "impact": None,
        "kind": None,
        "classification": "Unclassified",
        "action": None,
        "component": None,
        "cwe": None,
        "cid": None,
    },
    ["CID", "Classification", "Action"],
    {'filters': [
        {'columnKey': 'streams', 'matchMode': 'oneOrMoreMatch', 'matchers': [
            {'class': 'Stream', 'name': 'test_stream', 'type': 'nameMatcher'}
            ]
        },
        {'columnKey': 'classification', 'matchMode': 'oneOrMoreMatch', 'matchers': [
            {'type': 'keyMatcher', 'key': 'Unclassified'}
            ]
        }],
     'columns': ['cid', 'classification', 'action'],
     'snapshotScope': {
        'show': {'scope': 'last()', 'includeOutdatedSnapshots': False},
        'compareTo': {'scope': 'last()', 'includeOutdatedSnapshots': False}
    }}
)
