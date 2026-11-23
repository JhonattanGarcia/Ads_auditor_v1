"""Extension acotada del payload: fechas en todas las paginas de busqueda."""

from datetime import date
from .base import CollectorError


class ServerDateFilterMismatch(CollectorError):
    pass


def install_date_filter(client, minimum, maximum, callback=None):
    """Temporarily wrap GraphQL payload construction to inject dates on every search page."""
    low=date.fromisoformat(minimum) if minimum else None
    high=date.fromisoformat(maximum) if maximum else None
    if low is None: raise ValueError('A minimum start date is required')
    if high is not None and low>high: raise ValueError('Invalid start date range')
    interval={'min':low.isoformat(),'max':high.isoformat() if high else None}
    original=client._build_graphql_payload

    def build(doc_id, variables, friendly_name):
        """Inject the requested start-date range into search pagination payloads only."""
        if friendly_name=='AdLibrarySearchPaginationQuery':
            variables={**variables,'startDate':dict(interval)}
            if callback:
                callback({'startDate':dict(interval),'has_cursor':bool(variables.get('cursor'))})
        return original(doc_id=doc_id,variables=variables,friendly_name=friendly_name)

    client._build_graphql_payload=build
    return original
