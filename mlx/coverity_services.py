#!/usr/bin/python

'''Services and other utilities for Coverity scripting'''

# General
import csv
import logging
import re
try:
    # For Python 3.0 and later
    from urllib.error import URLError
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import URLError

# For Coverity - SOAP
from suds.client import Client
from suds.wsse import Security, UsernameToken

# -- Default values -- and global settings

DEFAULT_WS_VERSION = 'v9'

# Coverity built in Impact statuses
IMPACT_LIST = {'High', 'Medium', 'Low'}

KIND_LIST = {'QUALITY', 'SECURITY', 'TEST'}

# Coverity built in Classifications
CLASSIFICATION_LIST = {'Unclassified', 'Pending', 'False Positive', 'Intentional', 'Bug', 'Untested', 'No Test Needed'}

# Coverity built in Actions
ACTION_LIST = {'Undecided', 'Fix Required', 'Fix Submitted', 'Modeling Required', 'Ignore', 'On hold',
               'For Interest Only'}

ISSUE_KIND_2_LABEL = {'QUALITY': 'Quality', 'SECURITY': 'Security', 'Various': 'Quality/Security', 'TEST': 'Testing'}


# names of Coverity Triage/Attribute fields
EXT_REFERENCE_ATTR_NAME = "Ext. Reference"
DEFECT_STATUS_ATTR_NAME = "DefectStatus"
CLASSIFICATION_ATTR_NAME = "Classification"
ACTION_ATTR_NAME = "Action"
COMMENT_ATTR_NAME = "Comment"


def parse_two_part_term(term, delim=','):
    '''Parse a term assuming [ [part1],[part2] ]'''
    valid = False
    part1 = ""
    part2 = ""
    if term.find(delim) != -1:
        valid = True
        field1 = term.split(delim, 1)[0]
        if bool(field1):
            part1 = field1
        field2 = term.rsplit(delim, 1)[-1]
        if bool(field2):
            part2 = field2
    return valid, part1, part2


def compare_strings(str_a, str_b):
    '''Compare strings for equivalence

    some leniency allowed such as spaces and casing
    '''
    if re.match(str_b, str_a, flags=re.IGNORECASE):
        return True
    # ignore embedded spaces and some odd punctuation characters ("todo" = "To-Do")
    str_a2 = re.sub(r'[.:\-_ ]', '', str_a)
    str_b2 = re.sub(r'[:\-_ ]', '', str_b)  # don't remove dot (part of regex?)
    if re.match(str_b2, str_a2, flags=re.IGNORECASE):
        return True
    return False


class Service(object):
    '''
    Basic endpoint Service
    '''

    def __init__(self, transport, hostname, port, ws_version=DEFAULT_WS_VERSION):
        self.set_transport(transport)
        self.set_hostname(hostname)
        self.set_port(port)
        self.set_ws_version(ws_version)
        self.client = None

    def set_transport(self, transport):
        '''Set transport protocol'''
        self.transport = transport

    def get_transport(self):
        '''Get transport protocol'''
        return self.transport

    def set_hostname(self, hostname):
        '''Set hostname for service'''
        self.hostname = hostname

    def get_hostname(self):
        '''Get hostname for service'''
        return self.hostname

    def set_port(self, port):
        '''Set port for service'''
        self.port = port

    def get_port(self):
        '''Get port for service'''
        return self.port

    def set_ws_version(self, ws_version):
        '''Set WS version for service'''
        self.ws_version = ws_version

    def get_ws_version(self):
        '''Get WS version for service'''
        return self.ws_version

    def get_service_url(self, path=''):
        '''Get Service url with given path'''
        url = self.transport + '://' + self.hostname
        if bool(self.port):
            url += ':' + self.port
        if path:
            url += path
        return url

    def get_ws_url(self, service):
        '''Get WS url with given service'''
        return self.get_service_url('/ws/' + self.ws_version + '/' + service + '?wsdl')

    def login(self, username, password):
        '''Login to Coverity using given username and password'''
        security = Security()
        token = UsernameToken(username, password)
        security.tokens.append(token)
        self.client.set_options(wsse=security)


class CoverityConfigurationService(Service):
    '''
    Coverity Configuration Service (WebServices)
    '''

    def __init__(self, transport, hostname, port, ws_version=DEFAULT_WS_VERSION):
        super(CoverityConfigurationService, self).__init__(transport, hostname, port, ws_version)
        self.checkers = None
        url = self.get_ws_url('configurationservice')
        logging.getLogger('suds.client').setLevel(logging.CRITICAL)
        try:
            self.client = Client(url)
            logging.info("Validated presence of Coverity Configuration Service [%s]", url)
        except URLError:
            self.client = None
            logging.critical("No such Coverity Configuration Service [%s]", url)
            raise

    def login(self, username, password):
        '''Login to Coverity Configuration service using given username and password'''
        super(CoverityConfigurationService, self).login(username, password)
        version = self.get_version()
        if version is None:
            raise RuntimeError("Authentication to [%s] FAILED for [%s] account - check password"
                               % (self.get_service_url(), username))
        else:
            logging.info("Authentication to [%s] using [%s] account was OK - version [%s]",
                         self.get_service_url(), username, version.externalVersion)

    def get_version(self):
        '''Get the version of the service, can be used as a means to validate access permissions'''
        try:
            return self.client.service.getVersion()
        except URLError:
            return None

    @staticmethod
    def get_project_name(stream):
        '''Get the project name from the stream object'''
        return stream.primaryProjectId.name

    @staticmethod
    def get_triage_store(stream):
        '''Get the name of the triaging store from the stream object'''
        return stream.triageStoreId.name

    def get_stream(self, stream_name):
        '''Get the stream object from the stream name'''
        filter_spec = self.client.factory.create('streamFilterSpecDataObj')

        # use stream name as an initial glob pattern
        filter_spec.namePattern = stream_name

        # get all the streams that match
        streams = self.client.service.getStreams(filter_spec)

        # find the one with a matching name
        for stream in streams:
            if compare_strings(stream.id.name, stream_name):
                return stream
        return None

    # get a list of the snapshots in a named stream
    def get_snapshot_for_stream(self, stream_name):
        '''Get snapshot object for given stream name'''
        stream_id = self.client.factory.create('streamIdDataObj')
        stream_id.name = stream_name
        # optional filter specification
        filter_spec = self.client.factory.create('snapshotFilterSpecDataObj')
        # return a list of snapshotDataObj
        return self.client.service.getSnapshotsForStream(stream_id, filter_spec)

    @staticmethod
    def get_snapshot_id(snapshots, idx=1):
        '''Get the nth snapshot (base 1) - minus numbers to count from the end backwards (-1 = last)'''
        if bool(idx):
            num_snapshots = len(snapshots)
            if idx < 0:
                required = num_snapshots + idx + 1
            else:
                required = idx

            if abs(required) > 0 and abs(required) <= num_snapshots:
                # base zero
                return snapshots[required - 1].id
        return 0

    def get_snapshot_detail(self, snapshot_id):
        '''Get detailed information about a single snapshot'''
        snapshot = self.client.factory.create('snapshotIdDataObj')
        snapshot.id = snapshot_id
        # return a snapshotInfoDataObj
        return self.client.service.getSnapshotInformation(snapshot)

    def get_checkers(self):
        '''Get a list of checkers from the service'''
        if not self.checkers:
            self.checkers = self.client.service.getCheckerNames()
        return self.checkers

    @staticmethod
    def add_filter_rqt(name, req_csv, valid_list, filter_list, allow_regex=False):
        '''Lookup the list of given filter possibility, add to filter spec and return a validated list'''
        logging.info('Validate required %s [%s]', name, req_csv)
        validated = ""
        delim = ""
        for field in req_csv.split(','):
            if not valid_list or field in valid_list:
                logging.info('Classification [%s] is valid', field)
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
                logging.error('Invalid %s filter: %s', name, field)
        return validated


class CoverityDefectService(Service):
    '''
    Coverity Defect Service (WebServices)
    '''

    def __init__(self, config_service):
        '''Create a Defect Service, bound to the given Configuration Service'''
        super(CoverityDefectService, self).__init__(config_service.get_transport(),
                                                    config_service.get_hostname(),
                                                    config_service.get_port(),
                                                    config_service.get_ws_version())
        self.config_service = config_service
        self.filters = ""
        # logging.getLogger('suds.client').setLevel(logging.DEBUG)
        url = self.get_ws_url('defectservice')
        try:
            self.client = Client(url)
            logging.info("Validated presence of Coverity Defect Service [%s]", url)
        except URLError:
            self.client = None
            logging.critical("No such Coverity Defect Service [%s]", url)
            raise

    def get_defects(self, project, stream, checker=None, impact=None, kind=None, classification=None, action=None,
                    component=None, cwe=None, cid=None, custom=None):
        '''
        Get a list of defects for given stream, with some query criteria

        Arguments:
        project (str) - Name of the project to query
        stream (str) - Name of the stream to query
        checker (str) - A CSV list of the checker(s) to query
        impact (str) - A CSV list of the impact(s) to query
        kind (str) - A CSV list of the kind(s) to query
        classification (str) - A CSV list of the classification(s) to query
        action (str) - A CSV list of the action(s) to query
        component (str) - A CSV list of component(s) to include/exclude in the query
        exclude_component(bool) - True for excluding the given component(s), false for including them
        cwe (str) - A CSV list of the cwe(s) to query
        cid (str) - A CSV list of the cid(s) to query
        custom (str) - A custom query
        '''
        logging.info('Querying Coverity for defects in project [%s] stream [%s] ...', project, stream)

        # define the project
        project_id = self.client.factory.create('projectIdDataObj')
        project_id.name = project

        # and the stream
        stream_id = self.client.factory.create('streamIdDataObj')
        stream_id.name = stream

        # create filter spec
        filter_spec = self.client.factory.create('snapshotScopeDefectFilterSpecDataObj')

        # only for this stream
        filter_spec.streamIncludeNameList.append(stream_id)

        # apply any filter on checker names
        if checker:
            self.config_service.get_checkers()
            self.handle_filter_attribute(checker,
                                         'Checker',
                                         self.config_service.checkers,
                                         filter_spec.checkerList,
                                         allow_regex=True)

        # apply any filter on impact status
        if impact:
            self.handle_filter_attribute(impact, 'Impact', IMPACT_LIST, filter_spec.impactNameList)

        # apply any filter on issue kind
        if kind:
            self.handle_filter_attribute(kind, 'Kind', KIND_LIST, filter_spec.issueKindList)

        # apply any filter on classification
        if classification:
            self.handle_filter_attribute(classification,
                                         'Classification',
                                         CLASSIFICATION_LIST,
                                         filter_spec.classificationNameList)

        # apply any filter on action
        if action:
            self.handle_filter_attribute(action, 'Action', ACTION_LIST, filter_spec.actionNameList)

        # apply any filter on Components
        if component:
            logging.info('Using Component filter [%s]', component)
            parser = csv.reader([component])

            for fields in parser:
                for _, field in enumerate(fields):
                    field = field.strip()
                    component_id = self.client.factory.create('componentIdDataObj')
                    component_id.name = field
                    filter_spec.componentIdList.append(component_id)
            self.filters += ("<Components(%s)> " % (component))

        # apply any filter on CWE values
        if cwe:
            self.handle_filter_attribute(cwe, 'CWE', None, filter_spec.cweList)

        # apply any filter on CID values
        if cid:
            self.handle_filter_attribute(cid, 'CID', None, filter_spec.cidList)

        # if a special custom attribute value requirement
        if custom:
            self.handle_custom_filter_attribute(custom, filter_spec)

        # create page spec
        page_spec = self.client.factory.create('pageSpecDataObj')
        page_spec.pageSize = 9999
        page_spec.sortAscending = True
        page_spec.startIndex = 0

        # create snapshot scope
        snapshot_scope = self.client.factory.create('snapshotScopeSpecDataObj')

        snapshot_scope.showOutdatedStreams = False
        snapshot_scope.compareOutdatedStreams = False

        snapshot_scope.showSelector = 'last()'
        snapshot_scope.compareSelector = 'last()'

        logging.info('Running Coverity query...')
        return self.client.service.getMergedDefectsForSnapshotScope(project_id, filter_spec,
                                                                    page_spec, snapshot_scope)

    def handle_filter_attribute(self, attribute, name, *args, **kwargs):
        """ Applies any filter on an attribute's values.

        Args:
            attribute (str): A CSV list of attribute values to query.
            name (str): String representation of the attribute.
        """
        logging.info('Using %s filter [%s]', name, attribute)
        validated = self.config_service.add_filter_rqt(name, attribute, *args, **kwargs)
        logging.info('Resolves to [%s]', validated)
        if validated:
            self.filters += ("<%s(%s)> " % (name, validated))

    def handle_custom_filter_attribute(self, custom, filter_spec):
        """ Handles a custom attribute definition, and adds it to the filter spec if it's valid.

        Args:
            custom (str): A custom query.
            filter_spec (sudsobject.Factory): Object to store filter attributes.

        Raises:
            ValueError: Invalid custom attribute definition.
        """
        logging.info('Using attribute filter [%s]', custom)
        # split the name:value[;name:value1[,value2]]
        for fields in csv.reader([custom], delimiter=';'):
            for i, name_value_pair in enumerate(fields):
                name_value_pair = name_value_pair.strip()
                valid, name, values = parse_two_part_term(name_value_pair, ':')
                if valid:
                    logging.info("attr (%d) [%s] = any of ...", i + 1, name)

                    attribute_definition_id = self.client.factory.create('attributeDefinitionIdDataObj')
                    attribute_definition_id.name = name

                    filter_map = self.client.factory.create('attributeDefinitionValueFilterMapDataObj')
                    filter_map.attributeDefinitionId = attribute_definition_id

                    self._append_multiple_values(values, filter_map)

                    filter_spec.attributeDefinitionValueFilterMap.append(filter_map)
                else:
                    raise ValueError('Invalid custom attribute definition [%s]' % name_value_pair)
        self.filters += ("<Attrs(%s)> " % custom)

    def _append_multiple_values(self, values, filter_map):
        # if there are multiple values delimited with comma
        for value_fields in csv.reader([values], delimiter=','):
            for _, value in enumerate(value_fields):
                logging.info("             [%s]", value)

                attribute_value_id = self.client.factory.create('attributeValueIdDataObj')
                attribute_value_id.name = value

                filter_map.attributeValueIds.append(attribute_value_id)

    def get_defect(self, cid, stream):
        '''Get the details pertaining a specific CID - it may not have defect instance details if newly eliminated
        (fixed)'''
        logging.info('Fetching data for CID [%s] in stream [%s] ...', cid, stream)

        merged_defect_id = self.client.factory.create('mergedDefectIdDataObj')
        merged_defect_id.cid = cid

        filter_spec = self.client.factory.create('streamDefectFilterSpecDataObj')
        filter_spec.includeDefectInstances = True
        filter_spec.includeHistory = True

        stream_id = self.client.factory.create('streamIdDataObj')
        stream_id.name = stream
        filter_spec.streamIdList.append(stream_id)

        return self.client.service.getStreamDefects(merged_defect_id, filter_spec)

    def add_attribute_name_and_value(self, defect_state_spec, attr_name, attr_value):
        '''Add attribute name and value to given defect state specification'''

        # name value pair to update
        attribute_definition_id = self.client.factory.create('attributeDefinitionIdDataObj')
        attribute_definition_id.name = attr_name

        attribute_value_id = self.client.factory.create('attributeValueIdDataObj')
        attribute_value_id.name = attr_value

        # wrap the name/value pair
        defect_state_attr_value = self.client.factory.create('defectStateAttributeValueDataObj')
        defect_state_attr_value.attributeDefinitionId = attribute_definition_id
        defect_state_attr_value.attributeValueId = attribute_value_id

        # add to our list
        defect_state_spec.defectStateAttributeValues.append(defect_state_attr_value)

    # update the external reference id to a third party
    def update_ext_reference_attribute(self, cid, triage_store, ext_ref_id, ccomment=None):
        '''Update external reference attribute for given CID'''
        logging.info('Updating Coverity - CID [%s] in TS [%s] with Ext Ref [%s]', cid, triage_store, ext_ref_id)

        # triage store identifier
        triage_store_id = self.client.factory.create('triageStoreIdDataObj')
        triage_store_id.name = triage_store

        # CID to update
        merged_defect_id = self.client.factory.create('mergedDefectIdDataObj')
        merged_defect_id.cid = cid

        # if an ext ref id value supplied
        if bool(ext_ref_id):
            attr_value = ext_ref_id
            comment_value = 'Automatically recorded reference to new JIRA ticket.'
        else:
            # set to a space - which works as a blank without the WS complaining :-)
            attr_value = " "
            comment_value = 'Automatically cleared former JIRA ticket reference.'

        # if a Coverity comment to tag on the end
        if bool(ccomment):
            comment_value += " " + ccomment
        logging.info('Comment = [%s]', comment_value)

        defect_state_spec = self.client.factory.create('defectStateSpecDataObj')

        # name value pairs to add to this update
        self.add_attribute_name_and_value(defect_state_spec, EXT_REFERENCE_ATTR_NAME, attr_value)
        self.add_attribute_name_and_value(defect_state_spec, COMMENT_ATTR_NAME, comment_value)

        # apply the update
        return self.client.service.updateTriageForCIDsInTriageStore(triage_store_id, merged_defect_id,
                                                                    defect_state_spec)

    @staticmethod
    def get_instance_impact(stream_defect, instance_number=1):
        '''Get the current impact of the 'nth' incident of this issue (High/Medium/Low)'''
        counter = instance_number
        for instance in stream_defect.defectInstances:
            counter -= 1
            if counter == 0:
                return instance.impact.name
        return ""

    @staticmethod
    def get_value_for_named_attribute(stream_defect, attr_name):
        '''Lookup the value of a named attribute'''
        logging.info('Get value for cov attribute [%s]', attr_name)
        for attr_value in stream_defect.defectStateAttributeValues:
            if compare_strings(attr_value.attributeDefinitionId.name, attr_name):
                logging.info('Resolves to [%s]', attr_value.attributeValueId.name)
                return str(attr_value.attributeValueId.name)
        logging.warning('Value for attribute [%s] not found', attr_name)
        return ""

    @staticmethod
    def get_event_attribute_value(defect_state, name, value=None):
        '''Get specified attribute was set to given matching value'''
        if bool(value):
            logging.info('Searching for attribute [%s] with value [%s]', name, value)
        else:
            logging.info('Searching for attribute [%s]', name)

        for attr_value in defect_state.defectStateAttributeValues:
            # check if we have the named attribute
            if compare_strings(attr_value.attributeDefinitionId.name, name):
                # if any value supplied or it matches requirement
                if bool(attr_value.attributeValueId.name) and\
                   (not value or compare_strings(attr_value.attributeValueId.name, value)):
                    logging.info('Found [%s] = [%s]',
                                 attr_value.attributeDefinitionId.name, attr_value.attributeValueId.name)
                    return True, attr_value.attributeValueId.name
                # break attribute name search - either no value or it doesn't match
                break
        logging.warning('Event for attribute [%s] not found', name)
        return False, None

    def seek_nth_match(self, event_history, nth_event, attr_name, attr_value):
        '''Seek for a given attribute name-value pair in the triaging history'''
        num_match = 0
        for defect_state in event_history:
            # look for the attribute name-value pair in this triage event
            req_event_found, req_attr_value = self.get_event_attribute_value(defect_state, attr_name, attr_value)
            if req_event_found:
                num_match += 1
                # correct one?
                if num_match == nth_event:
                    return True, defect_state, req_attr_value
        return False, None, None

    def get_event_for_attribute_change(self, stream_defect, nth_term, attr_name, attr_value=None):
        '''Get event when specified attribute was set to given matching value'''
        logging.info('Searching for triage event n=[%d] where attribute [%s] is set to [%s]',
                     nth_term, attr_name, attr_value)

        if nth_term > 0:
            found, defect_state, value = self.seek_nth_match(stream_defect.history, nth_term, attr_name, attr_value)
        else:
            found, defect_state, value = self.seek_nth_match(reversed(stream_defect.history), abs(int(nth_term)),
                                                             attr_name, attr_value)

        return found, defect_state, value

    def get_ext_reference_id(self, stream_defect):
        '''Get external reference ID attribute value for given defect'''
        return self.get_value_for_named_attribute(stream_defect, EXT_REFERENCE_ATTR_NAME)

    def get_defect_status(self, stream_defect):
        '''Get defect status attribute value for given defect'''
        return self.get_value_for_named_attribute(stream_defect, DEFECT_STATUS_ATTR_NAME)

    def get_classification(self, stream_defect):
        '''Get classification attribute value for given defect'''
        return self.get_value_for_named_attribute(stream_defect, CLASSIFICATION_ATTR_NAME)

    def get_action(self, stream_defect):
        '''Get action attribute value for given defect'''
        return self.get_value_for_named_attribute(stream_defect, ACTION_ATTR_NAME)

    def get_defect_url(self, stream, cid):
        '''Get URL for given defect CID
        http://machine1.eng.company.com:8080/query/defects.htm?stream=StreamA&cid=1234
        '''
        return self.get_service_url('/query/defects.htm?stream=%s&cid=%s' % (stream, str(cid)))


if __name__ == '__main__':
    print("Sorry, no main here")
