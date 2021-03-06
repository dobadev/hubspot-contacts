##############################################################################
#
# Copyright (c) 2014, 2degrees Limited.
# All Rights Reserved.
#
# This file is part of hubspot-contacts
# <https://github.com/2degrees/hubspot-contacts>, which is subject to the
# provisions of the BSD at
# <http://dev.2degreesnetwork.com/p/2degrees-license.html>. A copy of the
# license should accompany this distribution. THIS SOFTWARE IS PROVIDED "AS IS"
# AND ANY AND ALL EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST
# INFRINGEMENT, AND FITNESS FOR A PARTICULAR PURPOSE.
#
##############################################################################

from abc import ABCMeta
from abc import abstractmethod
from abc import abstractproperty
from datetime import date
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from inspect import isgenerator
from itertools import islice

from hubspot.connection.exc import HubspotClientError
from hubspot.connection.exc import HubspotServerError
from hubspot.connection.testing import MockPortalConnection
from nose.tools import assert_equal
from nose.tools import assert_not_in
from nose.tools import assert_raises
from nose.tools import assert_raises_regexp
from nose.tools import eq_
from nose.tools import ok_
from voluptuous import Invalid

from hubspot.contacts import Contact
from hubspot.contacts._constants import BATCH_RETRIEVAL_SIZE_LIMIT
from hubspot.contacts._constants import BATCH_SAVING_SIZE_LIMIT
from hubspot.contacts.lists import ContactList
from hubspot.contacts.lists import add_contacts_to_list
from hubspot.contacts.lists import create_static_contact_list
from hubspot.contacts.lists import delete_contact_list
from hubspot.contacts.lists import get_all_contact_lists
from hubspot.contacts.lists import get_all_contacts
from hubspot.contacts.lists import get_all_contacts_by_last_update
from hubspot.contacts.lists import get_all_contacts_from_list
from hubspot.contacts.lists import get_all_contacts_from_list_by_added_date
from hubspot.contacts.lists import remove_contacts_from_list
from hubspot.contacts.properties import StringProperty
from hubspot.contacts.testing import AddContactsToList
from hubspot.contacts.testing import CreateStaticContactList
from hubspot.contacts.testing import DeleteContactList
from hubspot.contacts.testing import GetAllContactLists
from hubspot.contacts.testing import GetAllContacts
from hubspot.contacts.testing import GetAllContactsByLastUpdate
from hubspot.contacts.testing import GetContactsFromListByAddedDate
from hubspot.contacts.testing import GetContactsFromList
from hubspot.contacts.testing import RemoveContactsFromList
from hubspot.contacts.testing import STUB_LAST_MODIFIED_DATETIME
from hubspot.contacts.testing import UnsuccessfulCreateStaticContactList
from hubspot.contacts.testing import UnsuccessfulGetAllContacts
from hubspot.contacts.testing import UnsuccessfulGetAllContactsByLastUpdate

from tests._utils import make_contact
from tests._utils import make_contacts
from tests.test_properties import STUB_BOOLEAN_PROPERTY
from tests.test_properties import STUB_DATE_PROPERTY
from tests.test_properties import STUB_DATETIME_PROPERTY
from tests.test_properties import STUB_ENUMERATION_PROPERTY
from tests.test_properties import STUB_NUMBER_PROPERTY
from tests.test_properties import STUB_PROPERTY
from tests.test_properties import STUB_STRING_PROPERTY


_STUB_CONTACT_LIST = ContactList(1, 'atestlist', False)


_EMAIL_PROPERTY = StringProperty(
    'email',
    'Email address',
    'The email address',
    'contactinformation',
    'text',
    )


class TestContactListsRetrieval(object):

    def test_no_contact_lists(self):
        with self._make_connection_with_contact_lists([]) as connection:
            contact_lists = list(get_all_contact_lists(connection))

        eq_([], contact_lists)

    def test_getting_existing_contact_lists_single_page(self):
        contact_lists = [_STUB_CONTACT_LIST]
        connection = self._make_connection_with_contact_lists(contact_lists)

        with connection:
            retrieved_contact_lists = list(get_all_contact_lists(connection))

        eq_(contact_lists, retrieved_contact_lists)

    def test_getting_existing_contact_lists_multiple_pages(self):
        contact_lists = []
        for index in range(0, BATCH_RETRIEVAL_SIZE_LIMIT + 1):
            contact_list = ContactList(
                index,
                'list{}'.format(index),
                True,
                )
            contact_lists.append(contact_list)

        connection = self._make_connection_with_contact_lists(contact_lists)
        with connection:
            retrieved_contact_lists = list(get_all_contact_lists(connection))

        eq_(contact_lists, retrieved_contact_lists)

    def test_is_generator(self):
        connection = self._make_connection_with_contact_lists([])

        contact_lists = get_all_contact_lists(connection)
        ok_(isgenerator(contact_lists))

    def test_unexpected_response(self):
        connection = MockPortalConnection(
            _simulate_get_all_contact_lists_with_unsupported_response,
            )

        with assert_raises(Invalid):
            with connection:
                list(get_all_contact_lists(connection))

    def _make_connection_with_contact_lists(self, contact_lists):
        simulator = GetAllContactLists(contact_lists)
        connection = MockPortalConnection(simulator)
        return connection


def _simulate_get_all_contact_lists_with_unsupported_response():
    api_calls = GetAllContactLists([_STUB_CONTACT_LIST])()
    for api_call in api_calls:
        for list_data in api_call.response_body_deserialization['lists']:
            del list_data['dynamic']
    return api_calls


class TestStaticContactListCreation(object):

    def test_name_doesnt_exist(self):
        simulator = CreateStaticContactList(_STUB_CONTACT_LIST.name)
        with MockPortalConnection(simulator) as connection:
            contact_list = create_static_contact_list(
                _STUB_CONTACT_LIST.name,
                connection,
                )

        eq_(_STUB_CONTACT_LIST, contact_list)

    def test_name_already_exists(self):
        exception = HubspotClientError('Whoops!', 1)
        simulator = UnsuccessfulCreateStaticContactList(
            _STUB_CONTACT_LIST.name,
            exception,
            )

        with assert_raises_regexp(HubspotClientError, str(exception)):
            with MockPortalConnection(simulator) as connection:
                create_static_contact_list(_STUB_CONTACT_LIST.name, connection)

    def test_unexpected_response(self):
        connection = MockPortalConnection(
            _simulate_create_static_contact_list_with_unsupported_response,
            )

        with assert_raises(Invalid):
            with connection:
                create_static_contact_list(_STUB_CONTACT_LIST.name, connection)


def _simulate_create_static_contact_list_with_unsupported_response():
    api_calls = CreateStaticContactList(_STUB_CONTACT_LIST.name)()
    for api_call in api_calls:
        created_contact_list_data = api_call.response_body_deserialization
        del created_contact_list_data['dynamic']

    return api_calls


class TestContactListDeletion(object):

    def test_successful_deletion(self):
        simulator = DeleteContactList(_STUB_CONTACT_LIST.id)
        with MockPortalConnection(simulator) as connection:
            delete_contact_list(_STUB_CONTACT_LIST.id, connection)

    def test_valid_contact_list_id(self):
        """
        It must be possible to cast the ID of the contact list to an integer,
        since these are the only valid types of ID.

        """
        valid_contact_list_id = '123'
        simulator = DeleteContactList(valid_contact_list_id)
        with MockPortalConnection(simulator) as connection:
            delete_contact_list(valid_contact_list_id, connection)

    def test_invalid_contact_list_id(self):
        """
        When the contact list ID cannot be cast to an integer, the error
        is allowed to propagate.

        """
        with MockPortalConnection() as connection:
            with assert_raises(ValueError):
                invalid_contact_list_id = 'not an integer'
                delete_contact_list(invalid_contact_list_id, connection)


class _BaseContactListMembershipUpdateTestCase(object):

    __metaclass__ = ABCMeta

    _SIMULATOR_CLASS = abstractproperty()

    def test_no_contacts(self):
        contacts_in_list = make_contacts(5)
        self._test_membership_update([], [], contacts_in_list)

    @abstractmethod
    def test_contacts_not_in_list_without_exceeding_batch_size_limit(self):
        pass

    @abstractmethod
    def test_contacts_not_in_list_exceeding_batch_size_limit(self):
        pass

    @abstractmethod
    def test_all_contacts_in_list_without_exceeding_batch_size_limit(self):
        pass

    @abstractmethod
    def test_all_contacts_in_list_exceeding_batch_size_limit(self):
        pass

    @abstractmethod
    def test_updated_contacts_in_first_batch_of_list(self):
        pass

    @abstractmethod
    def test_updated_contacts_in_subsequent_batch_of_list(self):
        pass

    def test_non_existing_contact(self):
        self._test_membership_update(
            expected_updated_contacts=[],
            contacts_to_update=make_contacts(1),
            contacts_in_hubspot=[],
            )

    def test_unexpected_response(self):
        connection = MockPortalConnection(self._make_unsupported_api_call())
        with connection, assert_raises(Invalid):
            self._MEMBERSHIP_UPDATER(
                _STUB_CONTACT_LIST,
                make_contacts(1),
                connection,
                )

    def test_contacts_as_a_generator(self):
        contacts = make_contacts(1)

        with self._make_connection(contacts, contacts) as connection:
            updated_contact_vids = self._MEMBERSHIP_UPDATER(
                _STUB_CONTACT_LIST,
                iter(contacts),
                connection,
                )

        expected_updated_contact_vids = _get_contact_vids(contacts)
        assert_equal(expected_updated_contact_vids, updated_contact_vids)

    def _test_membership_update(
        self,
        expected_updated_contacts,
        contacts_to_update,
        contacts_in_list=None,
        contacts_in_hubspot=None,
        ):
        if contacts_in_list is None:
            contacts_in_list = []

        if contacts_in_hubspot is None:
            contacts_in_hubspot = \
                set(contacts_to_update) | set(contacts_in_list)

        updated_contacts = self._calculate_updated_contacts(
            contacts_to_update,
            contacts_in_list,
            contacts_in_hubspot,
            )
        connection = self._make_connection(contacts_to_update, updated_contacts)
        with connection:
            added_contact_vids = self._MEMBERSHIP_UPDATER(
                _STUB_CONTACT_LIST,
                contacts_to_update,
                connection,
                )

        expected_updated_contact_vids = \
            _get_contact_vids(expected_updated_contacts)
        assert_equal(set(expected_updated_contact_vids), set(added_contact_vids))

    @abstractmethod
    def _calculate_updated_contacts(
        self,
        contacts_to_update,
        contacts_in_list,
        contacts_in_hubspot,
        ):
        pass

    def _make_connection(self, contacts_to_update, updated_contacts):
        simulator = self._SIMULATOR_CLASS(
            _STUB_CONTACT_LIST,
            contacts_to_update,
            updated_contacts,
            )
        connection = MockPortalConnection(simulator)
        return connection

    @classmethod
    def _make_unsupported_api_call(cls):
        api_calls_simulator = cls._SIMULATOR_CLASS(
            _STUB_CONTACT_LIST,
            make_contacts(1),
            [],
            )

        api_calls = api_calls_simulator()
        for api_call in api_calls:
            # Corrupt the response
            del api_call.response_body_deserialization['updated']

        return lambda: api_calls


class TestAddingContactsToList(_BaseContactListMembershipUpdateTestCase):

    _MEMBERSHIP_UPDATER = staticmethod(add_contacts_to_list)

    _SIMULATOR_CLASS = AddContactsToList

    def test_contacts_not_in_list_without_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT)
        self._test_membership_update(
            expected_updated_contacts=contacts,
            contacts_to_update=contacts,
            contacts_in_list=[],
            )

    def test_contacts_not_in_list_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)
        self._test_membership_update(
            expected_updated_contacts=contacts,
            contacts_to_update=contacts,
            contacts_in_list=[],
            )

    def test_all_contacts_in_list_without_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT)
        self._test_membership_update(
            expected_updated_contacts=[],
            contacts_to_update=contacts,
            contacts_in_list=contacts,
            )

    def test_all_contacts_in_list_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)
        self._test_membership_update(
            expected_updated_contacts=[],
            contacts_to_update=contacts,
            contacts_in_list=contacts,
            )

    def test_updated_contacts_in_first_batch_of_list(self):
        contacts_to_update = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)

        contacts_in_first_batch, other_contacts = \
            _split_list(contacts_to_update, 1)

        self._test_membership_update(
            expected_updated_contacts=contacts_in_first_batch,
            contacts_to_update=contacts_to_update,
            contacts_in_list=other_contacts,
            )

    def test_updated_contacts_in_subsequent_batch_of_list(self):
        contacts_to_update = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)

        contacts_in_first_batch, other_contacts = \
            _split_list(contacts_to_update, BATCH_SAVING_SIZE_LIMIT)

        self._test_membership_update(
            expected_updated_contacts=contacts_in_first_batch,
            contacts_to_update=contacts_to_update,
            contacts_in_list=other_contacts,
            )

    def _calculate_updated_contacts(
        self,
        contacts_to_update,
        contacts_in_list,
        contacts_in_hubspot,
        ):
        contacts_not_in_list = set(contacts_to_update) - set(contacts_in_list)
        updated_contacts = set(contacts_in_hubspot) & contacts_not_in_list
        return updated_contacts


class TestRemovingContactsFromList(_BaseContactListMembershipUpdateTestCase):

    _MEMBERSHIP_UPDATER = staticmethod(remove_contacts_from_list)

    _SIMULATOR_CLASS = RemoveContactsFromList

    def test_contacts_not_in_list_without_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT)
        self._test_membership_update(
            expected_updated_contacts=[],
            contacts_to_update=contacts,
            contacts_in_list=[],
            )

    def test_contacts_not_in_list_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)
        self._test_membership_update(
            expected_updated_contacts=[],
            contacts_to_update=contacts,
            contacts_in_list=[],
            )

    def test_all_contacts_in_list_without_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT)
        self._test_membership_update(
            expected_updated_contacts=contacts,
            contacts_to_update=contacts,
            contacts_in_list=contacts,
            )

    def test_all_contacts_in_list_exceeding_batch_size_limit(self):
        contacts = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)
        self._test_membership_update(
            expected_updated_contacts=contacts,
            contacts_to_update=contacts,
            contacts_in_list=contacts,
            )

    def test_updated_contacts_in_first_batch_of_list(self):
        contacts_to_update = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)

        contacts_in_first_batch = contacts_to_update[BATCH_SAVING_SIZE_LIMIT:]

        self._test_membership_update(
            expected_updated_contacts=contacts_in_first_batch,
            contacts_to_update=contacts_to_update,
            contacts_in_list=contacts_in_first_batch,
            )

    def test_updated_contacts_in_subsequent_batch_of_list(self):
        contacts_to_update = make_contacts(BATCH_SAVING_SIZE_LIMIT + 1)

        contacts_in_subsequent_batch = \
            contacts_to_update[:BATCH_SAVING_SIZE_LIMIT]

        self._test_membership_update(
            expected_updated_contacts=contacts_in_subsequent_batch,
            contacts_to_update=contacts_to_update,
            contacts_in_list=contacts_in_subsequent_batch,
            )

    def _calculate_updated_contacts(
        self,
        contacts_to_update,
        contacts_in_list,
        contacts_in_hubspot,
        ):
        updated_contacts = set(contacts_in_hubspot) & set(contacts_in_list)
        return updated_contacts


def _get_contact_vids(contacts):
    return [c.vid for c in contacts]


def _split_list(list_, index):
    return list_[:index], list_[index:]


class _BaseGettingContactsTestCase(object):

    __metaclass__ = ABCMeta

    _RETRIEVER = abstractproperty()

    _SIMULATOR_CLASS = abstractproperty()

    _CONTACT_LIST = abstractproperty()

    def test_no_contacts(self):
        self._check_contacts_from_simulated_retrieval_equal([], [])

    def test_not_exceeding_pagination_size(self):
        contacts_count = BATCH_RETRIEVAL_SIZE_LIMIT - 1
        contacts = make_contacts(contacts_count)
        self._check_contacts_from_simulated_retrieval_equal(contacts, contacts)

    @abstractmethod
    def test_exceeding_pagination_size(self):
        pass

    def test_getting_existing_properties(self):
        simulator_contacts = [
            make_contact(1, properties={STUB_PROPERTY.name: 'foo'}),
            make_contact(
                2,
                properties={STUB_PROPERTY.name: 'baz', 'p2': 'bar'},
                ),
            ]

        expected_contacts = _get_contacts_with_stub_property(simulator_contacts)

        self._check_contacts_from_simulated_retrieval_equal(
            simulator_contacts,
            expected_contacts,
            property_names=[STUB_PROPERTY.name],
            )

    def test_getting_email_address_as_property(self):
        contact_with_email = make_contact(1)
        contact_with_no_email = make_contact(2)
        contact_with_no_email.email_address = None
        simulator_contacts = [contact_with_email, contact_with_no_email]

        expected_contacts = \
            _get_contacts_with_email_property(simulator_contacts)

        kwargs = self._get_kwargs_for_email_property()

        connection = self._make_connection_for_contacts(
            simulator_contacts,
            available_property=_EMAIL_PROPERTY,
            **kwargs
            )

        with connection:
            # Trigger API calls by consuming iterator
            retrieved_contacts = \
                list(self._RETRIEVER(connection=connection, **kwargs))

        _assert_retrieved_contacts_equal(expected_contacts, retrieved_contacts)

    def test_conflicting_email_address_property(self):
        contact = make_contact(1, {_EMAIL_PROPERTY.name: 'other@example.com'})
        with assert_raises(AssertionError):
            self._make_connection_for_contacts(
                [contact],
                available_property=_EMAIL_PROPERTY,
                **self._get_kwargs_for_email_property()
                )

    @classmethod
    def _get_kwargs_for_email_property(cls):
        kwargs = {'property_names': [_EMAIL_PROPERTY.name]}
        if cls._CONTACT_LIST:
            kwargs['contact_list'] = cls._CONTACT_LIST
        return kwargs

    def test_getting_non_existing_properties(self):
        """Requesting non-existing properties fails silently in HubSpot"""
        contacts = make_contacts(BATCH_RETRIEVAL_SIZE_LIMIT)
        self._check_contacts_from_simulated_retrieval_equal(
            contacts,
            contacts,
            property_names=['undefined'],
            )

    def test_contacts_with_related_contact_vids(self):
        contacts = [make_contact(1, related_contact_vids=[2, 3])]
        self._check_contacts_from_simulated_retrieval_equal(contacts, contacts)

    #{ Property type casting

    def test_property_type_casting(self):
        test_cases_data = [
            (STUB_BOOLEAN_PROPERTY, 'true', True),
            (STUB_DATE_PROPERTY, u'1396569600000', date(2014, 4, 4)),
            (
                STUB_DATETIME_PROPERTY,
                u'1396607280140',
                datetime(2014, 4, 4, 10, 28, 0, 140000),
                ),
            (STUB_ENUMERATION_PROPERTY, 'value1', 'value1'),
            (STUB_NUMBER_PROPERTY, '1.01', Decimal('1.01')),
            (STUB_STRING_PROPERTY, u'value', u'value'),
            ]

        for property_, raw_value, expected_value in test_cases_data:
            retrieved_contact = self._retrieve_contact_with_specified_property(
                property_,
                raw_value,
                )
            retrieved_property_value = \
                retrieved_contact.properties[property_.name]

            yield eq_, expected_value, retrieved_property_value

    def test_unset_property_type_casting(self):
        properties = (
            STUB_BOOLEAN_PROPERTY,
            STUB_DATE_PROPERTY,
            STUB_DATETIME_PROPERTY,
            STUB_ENUMERATION_PROPERTY,
            STUB_NUMBER_PROPERTY,
            STUB_STRING_PROPERTY,
            )

        for property_definition in properties:
            yield self._assert_unset_property_absent, property_definition

    def test_simulator_type_casting(self):
        enumeration_property_value = \
            list(STUB_ENUMERATION_PROPERTY.options.values())[0]

        properties_and_values = (
            (STUB_BOOLEAN_PROPERTY, True),
            (STUB_DATE_PROPERTY, date(2014, 1, 1)),
            (STUB_DATETIME_PROPERTY, datetime(2014, 1, 1, 7, 57)),
            (STUB_NUMBER_PROPERTY, 42),
            (STUB_STRING_PROPERTY, 'string'),
            (STUB_ENUMERATION_PROPERTY, enumeration_property_value),
            )

        for property_, property_value in properties_and_values:
            retrieved_contact = \
                self._retrieve_contact_with_specified_property(
                    property_,
                    property_value,
                    )
            retrieved_property_value = \
                retrieved_contact.properties[property_.name]
            yield eq_, property_value, retrieved_property_value

    def _retrieve_contact_with_specified_property(
        self,
        property_definition,
        property_value,
        **kwargs
        ):
        property_names = [property_definition.name]

        if self._CONTACT_LIST:
            kwargs['contact_list'] = self._CONTACT_LIST

        simulator_contact = \
            make_contact(1, {property_definition.name: property_value})
        connection = self._make_connection_for_contacts(
            contacts=[simulator_contact],
            available_property=property_definition,
            property_names=property_names,
            **kwargs
            )

        with connection:
            # Trigger API calls by consuming iterator
            retrieved_contacts = list(
                self._RETRIEVER(
                    connection=connection,
                    property_names=property_names,
                    **kwargs
                    ),
                )

        retrieved_contact = retrieved_contacts[0]
        return retrieved_contact

    def _assert_unset_property_absent(self, property_definition):
        retrieved_contact = self._retrieve_contact_with_specified_property(
            property_definition,
            '',
            )
        assert_not_in(property_definition.name, retrieved_contact.properties)

    def test_property_type_casting_for_unknown_property(self):
        simulator_contact = make_contact(1, {'p1': 'yes'})
        expected_contact = simulator_contact.copy()
        expected_contact.properties = {}
        self._check_contacts_from_simulated_retrieval_equal(
            [simulator_contact],
            [expected_contact],
            )

    #}

    def _check_contacts_from_simulated_retrieval_equal(
        self,
        simulator_contacts,
        expected_contacts,
        **kwargs
        ):

        if self._CONTACT_LIST:
            kwargs['contact_list'] = self._CONTACT_LIST

        connection = \
            self._make_connection_for_contacts(simulator_contacts, **kwargs)

        with connection:
            # Trigger API calls by consuming iterator
            retrieved_contacts = \
                list(self._RETRIEVER(connection=connection, **kwargs))

        _assert_retrieved_contacts_equal(expected_contacts, retrieved_contacts)

    @classmethod
    def _make_connection_for_contacts(
        cls,
        contacts,
        available_property=None,
        **simulator_kwargs
        ):
        available_property = available_property or STUB_STRING_PROPERTY
        simulator = cls._SIMULATOR_CLASS(
            contacts=contacts,
            available_properties=[available_property],
            **simulator_kwargs
            )
        connection = MockPortalConnection(simulator)
        return connection


def _get_contacts_with_stub_property(contacts):
    contacts_with_stub_property = []
    for contact in contacts:
        contact_with_stub_property = Contact(
            contact.vid,
            contact.email_address,
            {STUB_PROPERTY.name: contact.properties[STUB_PROPERTY.name]},
            [],
            )
        contacts_with_stub_property.append(contact_with_stub_property)

    return contacts_with_stub_property


def _get_contacts_with_email_property(simulator_contacts):
    contacts_with_email_property = []
    for contact in simulator_contacts:
        contact_properties = {}
        if contact.email_address:
            contact_properties['email'] = contact.email_address
        contact_with_email_property = Contact(
            contact.vid,
            contact.email_address,
            contact_properties,
            [],
            )
        contacts_with_email_property.append(contact_with_email_property)

    return contacts_with_email_property


def _assert_retrieved_contacts_equal(expected_contacts, retrieved_contacts):
    contacts_with_lastmodifieddate = \
        _derive_contacts_with_lastmodifieddate(expected_contacts)
    eq_(contacts_with_lastmodifieddate, retrieved_contacts)


def _derive_contacts_with_lastmodifieddate(original_contacts):
    contacts = []
    for original_contact in original_contacts:
        contact = original_contact.copy()
        contact.properties = dict(
            original_contact.properties,
            lastmodifieddate=STUB_LAST_MODIFIED_DATETIME,
            )
        contacts.append(contact)
    return contacts


class TestGettingAllContacts(_BaseGettingContactsTestCase):

    _RETRIEVER = staticmethod(get_all_contacts)

    _SIMULATOR_CLASS = GetAllContacts

    _CONTACT_LIST = None

    def test_exceeding_pagination_size(self):
        contacts_count = BATCH_RETRIEVAL_SIZE_LIMIT + 1
        contacts = make_contacts(contacts_count)
        self._check_contacts_from_simulated_retrieval_equal(contacts, contacts)


class _BaseTestUnsuccessfulGettingAllContacts(object):

    __metaclass__ = ABCMeta

    _RETRIEVER = abstractproperty()

    _SIMULATOR_CLASS = abstractproperty()

    def test_no_successfully_retrieved_contacts(self):
        connection = self._make_connection([])
        with connection:
            with assert_raises(HubspotServerError):
                list(self._RETRIEVER(connection))

    def test_some_successfully_retrieved_contacts(self):
        contacts = make_contacts(1)

        connection = self._make_connection(contacts)
        with connection:
            retrieved_contacts = self._RETRIEVER(connection)

            successufully_retrieved_contacts = \
                islice(retrieved_contacts, len(contacts))
            _assert_retrieved_contacts_equal(
                contacts,
                list(successufully_retrieved_contacts),
                )

            with assert_raises(HubspotServerError):
                next(retrieved_contacts)

    @classmethod
    def _make_connection(cls, contacts):
        simulator = cls._make_simulator(contacts)
        connection = MockPortalConnection(simulator)
        return connection

    @classmethod
    def _make_simulator(cls, contacts):
        simulator = cls._SIMULATOR_CLASS(
            contacts,
            HubspotServerError('Internal server error', 500),
            [STUB_STRING_PROPERTY],
            )
        return simulator


class TestUnsuccessfulGettingAllContacts(
    _BaseTestUnsuccessfulGettingAllContacts,
    ):

    _RETRIEVER = staticmethod(get_all_contacts)

    _SIMULATOR_CLASS = UnsuccessfulGetAllContacts


class TestGettingAllContactsByLastUpdate(_BaseGettingContactsTestCase):

    _RETRIEVER = staticmethod(get_all_contacts_by_last_update)

    _SIMULATOR_CLASS = GetAllContactsByLastUpdate

    _CONTACT_LIST = None

    def test_exceeding_pagination_size(self):
        contacts = make_contacts(BATCH_RETRIEVAL_SIZE_LIMIT + 1)
        self._check_contacts_from_simulated_retrieval_equal(contacts, contacts)

    def test_duplicated_contacts(self):
        contact1, contact2 = make_contacts(2)
        expected_contacts = [contact1, contact2]
        simulator_contacts = [contact1, contact2, contact1]

        self._check_contacts_from_simulated_retrieval_equal(
            simulator_contacts,
            expected_contacts,
            )

    def test_single_page_with_cutoff(self):
        contacts = make_contacts(BATCH_RETRIEVAL_SIZE_LIMIT - 1)
        page_1_contact_2 = contacts[1]
        self._check_retrieved_contacts_are_newer_than_contact(
            page_1_contact_2,
            contacts,
            )

    def test_multiple_pages_with_cutoff_on_first_page(self):
        contacts = make_contacts(BATCH_RETRIEVAL_SIZE_LIMIT + 1)
        page_1_last_contact = contacts[BATCH_RETRIEVAL_SIZE_LIMIT - 1]
        self._check_retrieved_contacts_are_newer_than_contact(
            page_1_last_contact,
            contacts,
            )

    def test_multiple_pages_with_cutoff_on_subsequent_page(self):
        contacts = make_contacts(BATCH_RETRIEVAL_SIZE_LIMIT + 2)
        page_2_contact_2 = contacts[BATCH_RETRIEVAL_SIZE_LIMIT + 1]
        self._check_retrieved_contacts_are_newer_than_contact(
            page_2_contact_2,
            contacts,
            )

    def test_cutoff_newer_than_most_recently_updated_contact(self):
        contacts = make_contacts(BATCH_RETRIEVAL_SIZE_LIMIT - 1)
        page_1_contact_1 = contacts[0]
        self._check_retrieved_contacts_are_newer_than_contact(
            page_1_contact_1,
            contacts,
            )

    def _check_retrieved_contacts_are_newer_than_contact(
        self,
        contact,
        simulator_contacts,
        ):
        contact_added_at_datetime = \
            self._SIMULATOR_CLASS.get_contact_added_at_datetime(
                contact,
                simulator_contacts,
                )
        cutoff_datetime = contact_added_at_datetime + timedelta(milliseconds=1)

        contact_index = simulator_contacts.index(contact)
        expected_contacts = simulator_contacts[:contact_index]

        self._check_contacts_from_simulated_retrieval_equal(
            simulator_contacts,
            expected_contacts,
            cutoff_datetime=cutoff_datetime,
            )


class TestUnsuccessfulGettingAllContactsByLastUpdate(
    _BaseTestUnsuccessfulGettingAllContacts,
    ):

    _RETRIEVER = staticmethod(get_all_contacts_by_last_update)

    _SIMULATOR_CLASS = UnsuccessfulGetAllContactsByLastUpdate


class TestGettingAllContactsFromList(_BaseGettingContactsTestCase):

    _RETRIEVER = staticmethod(get_all_contacts_from_list)

    _SIMULATOR_CLASS = GetContactsFromList

    _CONTACT_LIST = _STUB_CONTACT_LIST

    def test_exceeding_pagination_size(self):
        contacts_count = BATCH_RETRIEVAL_SIZE_LIMIT + 1
        contacts = make_contacts(contacts_count)
        self._check_contacts_from_simulated_retrieval_equal(contacts, contacts)


class TestGettingAllContactsFromListByAddedDate(
    TestGettingAllContactsByLastUpdate,
    ):

    _RETRIEVER = staticmethod(get_all_contacts_from_list_by_added_date)

    _SIMULATOR_CLASS = GetContactsFromListByAddedDate

    _CONTACT_LIST = _STUB_CONTACT_LIST
