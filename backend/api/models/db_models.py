from tortoise import fields, models


class BaseDBModel(models.Model):
    class Meta:
        abstract = True


class UserDBModel(BaseDBModel):
    id = fields.IntField(pk=True)
    userid = fields.CharField(max_length=255, unique=True)
    name = fields.CharField(max_length=255, null=True)
    pwd = fields.CharField(max_length=255)
    avatar = fields.TextField(null=True)
    email = fields.CharField(max_length=255, null=True)
    phone = fields.CharField(max_length=64, null=True)
    gender = fields.CharField(max_length=32, null=True)
    invite_code = fields.CharField(max_length=255, null=True)
    role = fields.CharField(max_length=255, null=True)
    apply_time = fields.CharField(max_length=255, null=True)
    last_login = fields.CharField(max_length=255, null=True)


class ResumeDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    userid = fields.CharField(max_length=255, unique=True, null=True)
    introduction = fields.JSONField(null=True)
    updated_at = fields.CharField(max_length=64, null=True)


class MemberDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255)
    grade = fields.CharField(max_length=255)
    session = fields.CharField(max_length=255)
    major = fields.CharField(max_length=255)
    title = fields.CharField(max_length=255)
    toWhere = fields.CharField(max_length=255)
    postAddress = fields.CharField(max_length=255)
    educations = fields.JSONField()
    teams = fields.JSONField()
    groups = fields.JSONField()
    introduction = fields.TextField(null=True)
    photo = fields.TextField(null=True)
    userid = fields.CharField(max_length=255, unique=True, null=True)
    awards = fields.JSONField()
    email = fields.CharField(max_length=255)
    mobile = fields.CharField(max_length=64)
    external = fields.TextField(null=True)


class ProductDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    tool_name = fields.CharField(max_length=255)
    tool_type = fields.CharField(max_length=255, null=True)
    organization = fields.CharField(max_length=255, null=True)
    homepage_url = fields.TextField(null=True)
    introduction = fields.TextField(null=True)
    audit_status = fields.CharField(max_length=64, null=True)
    publish_time = fields.CharField(max_length=255, null=True)
    update_time = fields.CharField(max_length=255, null=True)
    publisher_id = fields.CharField(max_length=255, null=True)


class ProjectDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255)
    info = fields.TextField(null=True)
    repo_type = fields.CharField(max_length=64, null=True)
    href = fields.TextField(null=True)
    icon = fields.TextField(null=True)
    favor = fields.BooleanField(default=False, db_default=False)
    audit_status = fields.CharField(max_length=64, null=True)
    publish_time = fields.CharField(max_length=255, null=True)
    update_time = fields.CharField(max_length=255, null=True)
    publisher_id = fields.CharField(max_length=255, null=True)


class ProductReviewDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    product = fields.ForeignKeyField('models.ProductDBModel', related_name='reviews', on_delete=fields.CASCADE)
    review = fields.TextField()
    reviewer_id = fields.CharField(max_length=255, null=True)
    review_time = fields.CharField(max_length=255, null=True)
    update_time = fields.CharField(max_length=255, null=True)


class ProductAttributeDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=255, unique=True)
    attribute_type = fields.CharField(max_length=64)
    create_time = fields.CharField(max_length=255, null=True)
    update_time = fields.CharField(max_length=255, null=True)


class ProductAttributeValueDBModel(BaseDBModel):
    id = fields.CharField(max_length=64, pk=True)
    product = fields.ForeignKeyField('models.ProductDBModel', related_name='attribute_values', on_delete=fields.CASCADE)
    attribute = fields.ForeignKeyField('models.ProductAttributeDBModel', related_name='values', on_delete=fields.CASCADE)
    value = fields.TextField(null=True)
    publisher_id = fields.CharField(max_length=255, null=True)
    publish_time = fields.CharField(max_length=255, null=True)
    update_time = fields.CharField(max_length=255, null=True)


class OIDCClient(BaseDBModel):
    client_id = fields.CharField(max_length=64, pk=True)
    name = fields.CharField(max_length=120)
    description = fields.TextField(default='')
    redirect_uris = fields.JSONField()
    client_type = fields.CharField(max_length=16)
    secret_hash = fields.TextField(null=True)
    enabled = fields.BooleanField(default=True, db_default=True)
    created_by = fields.CharField(max_length=255)
    created_at = fields.BigIntField()


class OIDCCode(BaseDBModel):
    code_hash = fields.CharField(max_length=64, pk=True)
    client = fields.ForeignKeyField('models.OIDCClient', related_name='codes', on_delete=fields.CASCADE)
    subject = fields.CharField(max_length=255)
    redirect_uri = fields.TextField()
    scope = fields.CharField(max_length=64)
    nonce = fields.CharField(max_length=512, null=True)
    challenge = fields.CharField(max_length=43)
    auth_time = fields.BigIntField()
    expires_at = fields.BigIntField(index=True)
    consumed = fields.BooleanField(default=False, db_default=False)


class OIDCAccessToken(BaseDBModel):
    token_hash = fields.CharField(max_length=64, pk=True)
    client = fields.ForeignKeyField('models.OIDCClient', related_name='tokens', on_delete=fields.CASCADE)
    subject = fields.CharField(max_length=255)
    scope = fields.CharField(max_length=64)
    expires_at = fields.BigIntField(index=True)
    grant_hash = fields.CharField(max_length=64, index=True)
