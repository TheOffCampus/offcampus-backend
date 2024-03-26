from jwt import PyJWKClient, decode

jwks_client = PyJWKClient('https://grand-skunk-35.clerk.accounts.dev/.well-known/jwks.json')

def get_user_id(token):
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    user_data = decode(
        token,
        signing_key.key,
        algorithms=['RS256'],
        audience='https://api.theoffcamp.us/v1/',
        options={
            'verify_aud': False,
            'verify_exp': False
        }
    )
    return user_data.get('sub')