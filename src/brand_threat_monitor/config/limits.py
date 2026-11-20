"""Validated per-search collection budgets shared by UI and CLI."""
DEFAULT_LIMITS={'max_scan':100,'max_pages':20,'max_duration':120,'idle_timeout':45}
BOUNDS={'max_scan':(1,100000),'max_pages':(1,10000),'max_duration':(1,86400),'idle_timeout':(1,3600)}


def validate_limits(values):
    if not isinstance(values,dict) or set(values)-set(DEFAULT_LIMITS):
        raise ValueError('Invalid collection limits')
    result={**DEFAULT_LIMITS,**values}
    for key,value in result.items():
        low,high=BOUNDS[key]
        if type(value) is not int or not low<=value<=high:
            raise ValueError(f'{key} must be an integer between {low} and {high}')
    return result
