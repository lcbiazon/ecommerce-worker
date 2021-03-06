"""Tests of sailthru worker code."""
import logging
from decimal import Decimal
from unittest import TestCase

from mock import patch
from sailthru.sailthru_error import SailthruClientError

from ecommerce_worker.sailthru.v1.tasks import update_course_enrollment, _update_unenrolled_list, _get_course_content
from ecommerce_worker.utils import get_configuration

log = logging.getLogger(__name__)

TEST_EMAIL = "test@edx.org"


class SailthruTests(TestCase):
    """
    Tests for the Sailthru tasks class.
    """

    def setUp(self):
        super(SailthruTests, self).setUp()
        self.course_id = 'edX/toy/2012_Fall'
        self.course_url = 'http://lms.testserver.fake/courses/edX/toy/2012_Fall/info'
        self.course_id2 = 'edX/toy/2016_Fall'
        self.course_url2 = 'http://lms.testserver.fake/courses/edX/toy/2016_Fall/info'

    @patch('ecommerce_worker.sailthru.v1.tasks.get_configuration')
    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    def test_sailthru_disabled(self, mock_log_error, mock_get_configuration):
        """Make sure nothing done and no error issued with disabled"""
        mock_get_configuration.return_value = {'SAILTHRU_ENABLE': False}
        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       True,
                                       'verified')
        self.assertFalse(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.get_configuration')
    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    def test_unspecified_key(self, mock_log_error, mock_get_configuration):
        # Test unspecified key
        mock_get_configuration.return_value = {'SAILTHRU_ENABLE': True}
        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       True,
                                       'verified',
                                       site_code='nonexistant_site')
        self.assertTrue(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_update_course_upgrade(self, mock_sailthru_api_post,
                                   mock_sailthru_api_get, mock_sailthru_purchase):
        """test add upgrade to cart"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       True,
                                       'verified',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=49)
        mock_sailthru_purchase.assert_called_with(TEST_EMAIL, [{'vars': {'course_run_id': self.course_id,
                                                                         'mode': 'verified',
                                                                         'upgrade_deadline_verified': '2020-03-12'},
                                                                'title': 'Course ' + self.course_id + ' mode: verified',
                                                                'url': self.course_url,
                                                                'price': 4900, 'qty': 1,
                                                                'id': self.course_id + '-verified'}],
                                                  options={'reminder_template': 'abandoned_template',
                                                           'reminder_time': '+60 minutes'},
                                                  incomplete=True, message_id='cookie_bid')

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_update_course_purchase(self, mock_sailthru_api_post,
                                    mock_sailthru_api_get, mock_sailthru_purchase):
        """test add purchase to cart"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'tags': 'tag1,tag2',
                                                                   'title': 'Course title'})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url2,
                                       True,
                                       'credit',
                                       course_id=self.course_id2,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=49)
        mock_sailthru_purchase.assert_called_with(TEST_EMAIL, [{'vars': {'course_run_id': self.course_id2,
                                                                         'mode': 'credit'},
                                                                'title': 'Course title',
                                                                'url': self.course_url2,
                                                                'tags': 'tag1,tag2',
                                                                'price': 4900, 'qty': 1,
                                                                'id': self.course_id2 + '-credit'}],
                                                  options={'reminder_template': 'abandoned_template',
                                                           'reminder_time': '+60 minutes'},
                                                  incomplete=True, message_id='cookie_bid')

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_update_course_purchase_complete(self, mock_sailthru_api_post,
                                             mock_sailthru_api_get, mock_sailthru_purchase):
        """test purchase complete"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       False,
                                       'credit',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=99)
        mock_sailthru_purchase.assert_called_with(TEST_EMAIL, [{'vars': {'course_run_id': self.course_id,
                                                                         'mode': 'credit',
                                                                         'upgrade_deadline_verified': '2020-03-12'},
                                                                'title': 'Course ' + self.course_id + ' mode: credit',
                                                                'url': self.course_url,
                                                                'price': 9900, 'qty': 1,
                                                                'id': self.course_id + '-credit'}],
                                                  options={'send_template': 'purchase_template'},
                                                  incomplete=False, message_id='cookie_bid')

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_update_course_upgrade_complete(self, mock_sailthru_api_post,
                                            mock_sailthru_api_get, mock_sailthru_purchase):
        """test upgrade complete"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       False,
                                       'verified',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=99)
        mock_sailthru_purchase.assert_called_with(TEST_EMAIL, [{'vars': {'course_run_id': self.course_id,
                                                                         'mode': 'verified',
                                                                         'upgrade_deadline_verified': '2020-03-12'},
                                                                'title': 'Course ' + self.course_id + ' mode: verified',
                                                                'url': self.course_url,
                                                                'price': 9900, 'qty': 1,
                                                                'id': self.course_id + '-verified'}],
                                                  options={'send_template': 'upgrade_template'},
                                                  incomplete=False, message_id='cookie_bid')

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_update_course_upgrade_complete_site(self, mock_sailthru_api_post,
                                                 mock_sailthru_api_get, mock_sailthru_purchase):
        """test upgrade complete with site code"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        # test upgrade complete with site code
        with patch('ecommerce_worker.configuration.test.SITE_OVERRIDES', get_configuration('TEST_SITE_OVERRIDES')):
            update_course_enrollment.delay(TEST_EMAIL,
                                           self.course_url,
                                           False,
                                           'verified',
                                           course_id=self.course_id,
                                           currency='USD',
                                           message_id='cookie_bid',
                                           unit_cost=Decimal(99.01),
                                           site_code='test_site')
        mock_sailthru_purchase.assert_called_with(TEST_EMAIL, [{'vars': {'course_run_id': self.course_id,
                                                                         'mode': 'verified',
                                                                         'upgrade_deadline_verified': '2020-03-12'},
                                                                'title': 'Course ' + self.course_id + ' mode: verified',
                                                                'url': self.course_url,
                                                                'price': 9901, 'qty': 1,
                                                                'id': self.course_id + '-verified'}],
                                                  options={'send_template': 'site_upgrade_template'},
                                                  incomplete=False, message_id='cookie_bid')

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_update_course_enroll(self, mock_sailthru_api_post,
                                  mock_sailthru_api_get, mock_sailthru_purchase):
        """test audit enroll"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       False,
                                       'audit',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=Decimal(0))
        mock_sailthru_purchase.assert_called_with(TEST_EMAIL, [{'vars': {'course_run_id': self.course_id,
                                                                         'mode': 'audit',
                                                                         'upgrade_deadline_verified': '2020-03-12'},
                                                                'title': 'Course ' + self.course_id + ' mode: audit',
                                                                'url': self.course_url,
                                                                'price': 100, 'qty': 1,
                                                                'id': self.course_id + '-audit'}],
                                                  options={'send_template': 'enroll_template'},
                                                  incomplete=False, message_id='cookie_bid')

    @patch('ecommerce_worker.sailthru.v1.tasks.get_configuration')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_update_course_enroll_skip(self, mock_sailthru_api_post,
                                       mock_sailthru_api_get, mock_sailthru_purchase,
                                       mock_get_configuration):
        """test audit enroll with configured cost = 0"""

        config = get_configuration('SAILTHRU')
        config['SAILTHRU_MINIMUM_COST'] = 0
        mock_get_configuration.return_value = config

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})
        mock_sailthru_purchase.return_value = MockSailthruResponse({'ok': True})

        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       False,
                                       'audit',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=Decimal(0))
        mock_sailthru_purchase.assert_not_called()

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_post')
    def test_purchase_api_error(self, mock_sailthru_api_post,
                                mock_sailthru_api_get, mock_sailthru_purchase, mock_log_error):
        """test purchase API error"""

        # create mocked Sailthru API responses
        mock_sailthru_api_post.return_value = MockSailthruResponse({'ok': True})
        mock_sailthru_api_get.return_value = MockSailthruResponse({'vars': {'upgrade_deadline_verified': '2020-03-12'}})

        mock_sailthru_purchase.return_value = MockSailthruResponse({}, error='error')
        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       False,
                                       'verified',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=Decimal(99))
        self.assertTrue(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.purchase')
    def test_purchase_api_exception(self,
                                    mock_sailthru_purchase, mock_log_error):
        """test purchase API exception"""
        mock_sailthru_purchase.side_effect = SailthruClientError
        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       False,
                                       'verified',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=Decimal(99))
        self.assertTrue(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.logger.error')
    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient.api_get')
    def test_user_get_error(self,
                            mock_sailthru_api_get, mock_log_error):
        # test error reading unenrolled list
        mock_sailthru_api_get.return_value = MockSailthruResponse({}, error='error', code=43)
        update_course_enrollment.delay(TEST_EMAIL,
                                       self.course_url,
                                       False,
                                       'honor',
                                       course_id=self.course_id,
                                       currency='USD',
                                       message_id='cookie_bid',
                                       unit_cost=Decimal(99))
        self.assertTrue(mock_log_error.called)

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient')
    def test_get_course_content(self, mock_sailthru_client):
        """
        test routine which fetches data from Sailthru content api
        """
        config = {'SAILTHRU_CACHE_TTL_SECONDS': 100}
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({"title": "The title"})
        response_json = _get_course_content('course:123', mock_sailthru_client, None, config)
        self.assertEquals(response_json, {"title": "The title"})
        mock_sailthru_client.api_get.assert_called_with('content', {'id': 'course:123'})

        # test second call uses cache
        mock_sailthru_client.reset_mock()
        response_json = _get_course_content('course:123', mock_sailthru_client, None, config)
        self.assertEquals(response_json, {"title": "The title"})
        mock_sailthru_client.api_get.assert_not_called()

        # test error from Sailthru
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({}, error='Got an error')
        self.assertEquals(_get_course_content('course:124', mock_sailthru_client, None, config), {})

        # test exception
        mock_sailthru_client.api_get.side_effect = SailthruClientError
        self.assertEquals(_get_course_content('course:125', mock_sailthru_client, None, config), {})

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient')
    def test_update_unenrolled_list_new(self, mock_sailthru_client):
        """
        test routine which updates the unenrolled list in Sailthru
        """

        # test a new unenroll
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': ['course_u1']}})
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, True))
        mock_sailthru_client.api_get.assert_called_with("user", {"id": TEST_EMAIL, "fields": {"vars": 1}})
        mock_sailthru_client.api_post.assert_called_with('user',
                                                         {'vars': {'unenrolled': ['course_u1', self.course_url]},
                                                          'id': TEST_EMAIL, 'key': 'email'})

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient')
    def test_update_unenrolled_list_old(self, mock_sailthru_client):
        # test an existing unenroll
        mock_sailthru_client.reset_mock()
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': [self.course_url]}})
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, True))
        mock_sailthru_client.api_get.assert_called_with("user", {"id": TEST_EMAIL, "fields": {"vars": 1}})
        mock_sailthru_client.api_post.assert_not_called()

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient')
    def test_update_unenrolled_list_reenroll(self, mock_sailthru_client):
        # test an enroll of a previously unenrolled course
        mock_sailthru_client.reset_mock()
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': [self.course_url]}})
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, False))
        mock_sailthru_client.api_post.assert_called_with('user',
                                                         {'vars': {'unenrolled': []},
                                                          'id': TEST_EMAIL, 'key': 'email'})

    @patch('ecommerce_worker.sailthru.v1.tasks.SailthruClient')
    def test_update_unenrolled_list_errors(self, mock_sailthru_client):
        # test get error from Sailthru
        mock_sailthru_client.reset_mock()
        # simulate retryable error
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({}, error='Got an error', code=43)
        self.assertFalse(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                 self.course_url, False))

        # test get error from Sailthru
        mock_sailthru_client.reset_mock()
        # simulate unretryable error
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({}, error='Got an error', code=1)
        self.assertTrue(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                self.course_url, False))

        # test post error from Sailthru
        mock_sailthru_client.reset_mock()
        mock_sailthru_client.api_post.return_value = MockSailthruResponse({}, error='Got an error', code=9)
        mock_sailthru_client.api_get.return_value = MockSailthruResponse({'vars': {'unenrolled': [self.course_url]}})
        self.assertFalse(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                 self.course_url, False))

        # test exception
        mock_sailthru_client.api_get.side_effect = SailthruClientError
        self.assertFalse(_update_unenrolled_list(mock_sailthru_client, TEST_EMAIL,
                                                 self.course_url, False))


class MockSailthruResponse(object):
    """
    Mock object for SailthruResponse
    """
    def __init__(self, json_response, error=None, code=1):
        self.json = json_response
        self.error = error
        self.code = code

    def is_ok(self):
        """
        Return true of no error
        """
        return self.error is None

    def get_error(self):
        """
        Get error description
        """
        return MockSailthruError(self.error, self.code)


class MockSailthruError(object):
    """
    Mock object for Sailthru Error
    """
    def __init__(self, error, code=1):
        self.error = error
        self.code = code

    def get_message(self):
        """
        Get error description
        """
        return self.error

    def get_error_code(self):
        """
        Get error code
        """
        return self.code
