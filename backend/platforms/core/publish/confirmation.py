from .not_ready import NotReady
from .published import Published
from .ready_to_commit import ReadyToCommit

type Confirmation = Published | NotReady | ReadyToCommit
