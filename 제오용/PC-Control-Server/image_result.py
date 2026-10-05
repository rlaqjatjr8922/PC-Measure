"""MCP images are image content blocks, never base64 text dumps."""
import base64
import capture_store
import json
from io import BytesIO
from PIL import Image
from mcp.types import CallToolResult, TextContent, ImageContent

def build(result):
    if isinstance(result, dict) and result.get('encoding') in ('base64', 'local_file') and result.get('content_type','').split(';')[0].startswith('image/'):
        result = dict(result)
        raw = capture_store.image_bytes(result)
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError('이미지가 너무 큽니다. 작은 영역을 캡처해 주세요.')
        with Image.open(BytesIO(raw)) as source:
            source.load()
            original = source.size
            picture = source.convert('RGB')
            picture.thumbnail((1920, 1920))
            out = BytesIO()
            picture.save(out, format='JPEG', quality=85)
            encoded = base64.b64encode(out.getvalue()).decode('ascii')
            meta = {k:v for k,v in result.items() if k not in ('data','encoding','content_type','bytes')}
            meta.update(original_width=original[0], original_height=original[1], width=picture.width, height=picture.height,
                        content_type='image/jpeg', bytes=len(out.getvalue()), coordinate_note='좌표는 원본 화면 기준입니다. 표시 이미지 좌표에 original_width/width, original_height/height를 곱하세요.')
        return CallToolResult(content=[TextContent(text=json.dumps(meta,ensure_ascii=False)), ImageContent(data=encoded,mime_type='image/jpeg')], structured_content=meta)
    return CallToolResult(content=[TextContent(text=json.dumps(result,ensure_ascii=False))], structured_content=result)
