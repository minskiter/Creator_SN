import datetime
from fastapi import Header
from api.models.body import response_body
from api.models.jwt_tool import decode_jwt
from functools import wraps
import inspect
from fastapi.responses import JSONResponse
from api.models.db_models import UserDBModel


def has_admin_role(role):
    return 'admin' in {item.strip() for item in (role or '').split(',')}

class Auth():

    def __init__(self, app_config, algorithms=['HS256']):
        self.app_config = app_config
        self.algorithms = algorithms
    
    @staticmethod
    def valid_user(token, jwt_key, algorithms=['HS256']):
        if token is None:
            return {
                    'status': 1,
                    'islogin': False,
                    'userid': None,
                    'role': None,
                    'message': 'no token info'
                }, False
        decode_item = decode_jwt(token, jwt_key, algorithms)
        now = datetime.datetime.now().timestamp()
        try:
            if now >= decode_item['exp']:
                return {
                    'status': 1,
                    'islogin': False,
                    'userid': None,
                    'role': None,
                    'message': 'expired'
                }, False
            return {
                'status': 0,
                'islogin': True,
                'userid': decode_item['userid'],
                'role': decode_item['role'],
                'message': ''
            }, True
        except:
            return {
                'status': 2,
                'islogin': False,
                'islogin': False,
                'userid': None,
                'role': None,
                'message': 'error'
            }, False
    
    async def is_user(self, api_key: str = Header(None)):
        valid_info, valid_status = Auth.valid_user(api_key, self.app_config['jwt_key'], self.algorithms)
        if not valid_status:
            return (False, response_body(code=403, status='failed', message=valid_info['message']))
        return (True, valid_info)
    
    async def is_admin(self, api_key: str = Header(None)):
        valid_info, valid_status = Auth.valid_user(api_key, self.app_config['jwt_key'], self.algorithms)
        if not valid_status:
            return (False, response_body(code=403, status='failed', message=valid_info['message']))
        if not await self.current_admin(valid_info):
            return (False, response_body(code=403, status='failed', message='permission denied'))
        return (True, valid_info)

    async def current_admin(self, valid_info):
        if valid_info['userid'] == self.app_config['root_name']:
            return has_admin_role(valid_info['role'])
        # Re-read permissions so removing admin takes effect for existing JWTs.
        user = await UserDBModel.get_or_none(userid=valid_info['userid'])
        return bool(user and has_admin_role(user.role))
    
    def require_user(self):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, api_key: str = Header(None), **kwargs):
                valid_info, valid_status = Auth.valid_user(api_key, self.app_config['jwt_key'], self.algorithms)
                if not valid_status:
                    res = response_body(code=403, status='failed', message=valid_info['message'])
                    return JSONResponse(
                        status_code=200,
                        content=res()
                    )

                # 把验证信息注入到 kwargs
                if 'valid_info' in kwargs:
                    kwargs["valid_info"] = valid_info
                return await func(*args, **kwargs)
            
            # 由于fastapi不传入api function中未定义的参数, 因此利用inspect获取api function并对其需要的参数进行篡改, 加入api_key
            sig = inspect.signature(func)
            if 'api_key' not in sig.parameters.values():
                params = list(sig.parameters.values())
                # 插入一个新的 api_key 参数
                api_key_param = inspect.Parameter(
                    "api_key",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=Header(None),
                    annotation=str
                )
            params.append(api_key_param)
            wrapper.__signature__ = sig.replace(parameters=params)
            return wrapper
        return decorator
    
    def require_admin(self):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, api_key: str = Header(None), **kwargs):
                valid_info, valid_status = Auth.valid_user(api_key, self.app_config['jwt_key'], self.algorithms)
                if not valid_status:
                    res = response_body(code=403, status='failed', message=valid_info['message'])
                    return JSONResponse(
                        status_code=200,
                        content=res()
                    )
                if not await self.current_admin(valid_info):
                    res = response_body(code=403, status='failed', message='permission denied')
                    return JSONResponse(
                        status_code=200,
                        content=res()
                    )

                # 把验证信息注入到 kwargs
                if 'valid_info' in kwargs:
                    kwargs["valid_info"] = valid_info
                return await func(*args, **kwargs)
            
            # 由于fastapi不传入api function中未定义的参数, 因此利用inspect获取api function并对其需要的参数进行篡改, 加入api_key
            sig = inspect.signature(func)
            if 'api_key' not in sig.parameters.values():
                params = list(sig.parameters.values())
                # 插入一个新的 api_key 参数
                api_key_param = inspect.Parameter(
                    "api_key",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=Header(None),
                    annotation=str
                )
            params.append(api_key_param)
            wrapper.__signature__ = sig.replace(parameters=params)
            return wrapper
        return decorator
