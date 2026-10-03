from .awaiting_confirmation import AwaitingConfirmation
from .published import Published
from .scheduled import Scheduled

type PublishOutcome = Published | Scheduled | AwaitingConfirmation
