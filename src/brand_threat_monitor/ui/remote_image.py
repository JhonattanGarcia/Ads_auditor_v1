"""Bounded web image previews; no evidence or database changes."""
from io import BytesIO
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import warnings
from PIL import Image, ImageOps

MAX_BYTES=8*1024*1024


def load_remote_image(url):
    parts=urlsplit(url)
    if parts.scheme not in {'http','https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Unsupported image URL')
    request=Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'image/*'})
    with urlopen(request,timeout=8) as response:
        if urlsplit(response.geturl()).scheme not in {'http','https'}:
            raise ValueError('Unsupported image redirect')
        content=response.read(MAX_BYTES+1)
    if len(content)>MAX_BYTES: raise ValueError('Image exceeds 8 MiB')
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(BytesIO(content),formats=['PNG','JPEG','WEBP','GIF']) as source:
            if source.width*source.height>20_000_000 or max(source.size)>12000:
                raise ValueError('Image dimensions exceed preview limit')
            image=ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((420,300))
    return image
