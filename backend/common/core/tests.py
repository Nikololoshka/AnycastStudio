import inspect

from asgiref.sync import async_to_sync
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from .decorators import precondition, precondition_with_params

REFUSED = HttpResponse("refused", status=403)


@precondition
def refuse_everything(request):
    return REFUSED


@precondition_with_params
def require_header(request, name):
    if name not in request.headers:
        return REFUSED


def view(request, item_id):
    return HttpResponse(f"item {item_id}")


async def async_view(request, item_id):
    return HttpResponse(f"item {item_id}")


class PreconditionScenarios(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/", headers={"X-Present": "1"})

    def test_a_refusing_check_answers_instead_of_the_view(self):
        response = refuse_everything(view)(self.request, item_id=7)

        self.assertIs(response, REFUSED)

    def test_a_passing_check_hands_the_url_arguments_to_the_view(self):
        response = require_header("X-Present")(view)(self.request, item_id=7)

        self.assertEqual(response.content, b"item 7")

    def test_parameters_are_bound_per_decorator(self):
        response = require_header("X-Missing")(view)(self.request, item_id=7)

        self.assertIs(response, REFUSED)

    def test_an_async_view_stays_async(self):
        # Given: an async view behind a passing check
        wrapped = require_header("X-Present")(async_view)

        # When: it is awaited
        response = async_to_sync(wrapped)(self.request, item_id=7)

        # Then: the view ran and the wrapper kept its coroutine nature
        self.assertEqual(response.content, b"item 7")
        self.assertTrue(inspect.iscoroutinefunction(wrapped))
