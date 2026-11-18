"""Validacion, previsualizacion e incorporacion de imagenes locales de evidencia."""

import hashlib
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings
from dataclasses import dataclass

from PIL import Image,ImageOps,UnidentifiedImageError

from ..config.operator import validate_actor
from ..review.service import audit

MAX_BYTES=20*1024*1024
MAX_PIXELS=20_000_000
FORMATS=['PNG','JPEG','WEBP','GIF']
EXTENSIONS={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp','GIF':'.gif'}


@dataclass
class Preview:
    image: object
    content: bytes
    sha256: str
    format: str
    width: int
    height: int
    animated: bool


def local_path(value):
    value=str(value)
    if value.startswith(('\\\\','//')) or '://' in value:
        raise ValueError('Only local files are supported; URLs and network paths are not opened')
    path=Path(value).absolute()
    for component in [path,*path.parents]:
        if component.is_symlink() or (hasattr(component,'is_junction') and component.is_junction()):
            raise ValueError('Linked files/directories are not supported')
    if not path.is_file(): raise ValueError('Evidence file is missing or is not a regular file')
    return path


def load_preview(value, *, expected_hash=None):
    path=local_path(value)
    if path.stat().st_size>MAX_BYTES: raise ValueError('Image exceeds the 20 MiB limit')
    with path.open('rb') as stream: content=stream.read(MAX_BYTES+1)
    if len(content)>MAX_BYTES: raise ValueError('Image exceeds the 20 MiB limit')
    sha=hashlib.sha256(content).hexdigest()
    if expected_hash and sha!=expected_hash: raise ValueError('Evidence hash mismatch; preview blocked')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(content),formats=FORMATS) as source:
                width,height=source.size
                if width*height>MAX_PIXELS or max(width,height)>12000:
                    raise ValueError('Image dimensions exceed the preview limit')
                format=source.format
                animated=bool(getattr(source,'is_animated',False))
                source.verify()
            with Image.open(BytesIO(content),formats=FORMATS) as source:
                source.seek(0)
                image=ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((640,480))
        return Preview(image,content,sha,format,width,height,animated)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
        raise ValueError('Unsupported, corrupt or oversized image. Use PNG, JPEG, WebP or GIF.') from exc


def attach_image(db,case_id,source,directory,*,actor,reason):
    actor=validate_actor(actor)
    if not reason or not reason.strip(): raise ValueError('An evidence note is required')
    preview=load_preview(source)
    directory=Path(directory).absolute()
    # Validate directory components before creating anything.
    for component in [directory,*directory.parents]:
        if component.is_symlink() or (hasattr(component,'is_junction') and component.is_junction()):
            raise ValueError('Linked evidence directories are not supported')
    if str(directory).startswith(('\\\\','//')): raise ValueError('Use a local evidence directory')
    evidence_id=str(uuid4())
    destination=directory/(evidence_id+EXTENSIONS[preview.format])
    created=False
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM review_cases WHERE case_id=?',(case_id,)).fetchone():
                raise ValueError('Unknown case')
            directory.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as stream:
                created=True; stream.write(preview.content)
            db.execute('INSERT INTO evidence(evidence_id,case_id,type,hash,local_path) VALUES (?,?,?,?,?)',
                       (evidence_id,case_id,'local_image',preview.sha256,str(destination)))
            audit(db,actor,'attach_image',case_id,None,{'evidence_id':evidence_id,'hash':preview.sha256,
                  'local_path':str(destination),'format':preview.format,'bytes':len(preview.content)},reason)
    except BaseException:
        if created: destination.unlink(missing_ok=True)
        raise
    return evidence_id
