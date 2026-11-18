"""Filtros compartidos; fechas de observacion en America/Bogota."""

from dataclasses import dataclass
from datetime import date,datetime
from zoneinfo import ZoneInfo
from ..config.profiles import COUNTRIES


def local_day(value):
    if not value: return None
    try:
        stamp=datetime.fromisoformat(value)
        if stamp.tzinfo is not None: stamp=stamp.astimezone(ZoneInfo('America/Bogota'))
        return stamp.date()
    except (ValueError,TypeError): return None


@dataclass(frozen=True)
class Filters:
    country: str | None = None
    criterion: str | None = None
    advertiser_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None

    def __post_init__(self):
        for field in ['country','criterion','advertiser_id','date_from','date_to']:
            value=getattr(self,field)
            if value is not None:
                if not isinstance(value,str): raise ValueError(f'{field}: expected text')
                object.__setattr__(self,field,value.strip() or None)
        if self.country:
            object.__setattr__(self,'country',self.country.upper())
            if self.country not in COUNTRIES: raise ValueError('Country must be a valid ISO code')
        for field in ['date_from','date_to']:
            value=getattr(self,field)
            if value:
                parsed=date.fromisoformat(value)
                if parsed.isoformat()!=value: raise ValueError('Use dates in YYYY-MM-DD format')
        if self.date_from and self.date_to and self.date_from>self.date_to:
            raise ValueError('From date must not be later than To date')

    def matches(self, *, country=None, criterion=None, advertiser_id=None, observed_at=None):
        if self.country and (country or '').upper()!=self.country: return False
        if self.criterion and self.criterion.casefold() not in (criterion or '').casefold(): return False
        if self.advertiser_id and advertiser_id!=self.advertiser_id: return False
        day=local_day(observed_at)
        if self.date_from and (day is None or day<date.fromisoformat(self.date_from)): return False
        if self.date_to and (day is None or day>date.fromisoformat(self.date_to)): return False
        return True

    @property
    def active(self):
        return any(getattr(self,k) for k in ['country','criterion','advertiser_id','date_from','date_to'])
