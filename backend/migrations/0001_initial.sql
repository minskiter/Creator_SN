-- Initial PostgreSQL schema. Immutable once applied.
CREATE TABLE IF NOT EXISTS "memberdbmodel" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "grade" VARCHAR(255) NOT NULL,
    "session" VARCHAR(255) NOT NULL,
    "major" VARCHAR(255) NOT NULL,
    "title" VARCHAR(255) NOT NULL,
    "toWhere" VARCHAR(255) NOT NULL,
    "postAddress" VARCHAR(255) NOT NULL,
    "educations" JSONB NOT NULL,
    "teams" JSONB NOT NULL,
    "groups" JSONB NOT NULL,
    "introduction" TEXT,
    "photo" TEXT,
    "userid" VARCHAR(255) UNIQUE,
    "awards" JSONB NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "mobile" VARCHAR(64) NOT NULL,
    "external" TEXT
);
CREATE TABLE IF NOT EXISTS "productattributedbmodel" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL UNIQUE,
    "attribute_type" VARCHAR(64) NOT NULL,
    "create_time" VARCHAR(255),
    "update_time" VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS "productdbmodel" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "tool_name" VARCHAR(255) NOT NULL,
    "tool_type" VARCHAR(255),
    "organization" VARCHAR(255),
    "homepage_url" TEXT,
    "introduction" TEXT,
    "audit_status" VARCHAR(64),
    "publish_time" VARCHAR(255),
    "update_time" VARCHAR(255),
    "publisher_id" VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS "productattributevaluedbmodel" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "value" TEXT,
    "publisher_id" VARCHAR(255),
    "publish_time" VARCHAR(255),
    "update_time" VARCHAR(255),
    "attribute_id" VARCHAR(64) NOT NULL REFERENCES "productattributedbmodel" ("id") ON DELETE CASCADE,
    "product_id" VARCHAR(64) NOT NULL REFERENCES "productdbmodel" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "productreviewdbmodel" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "review" TEXT NOT NULL,
    "reviewer_id" VARCHAR(255),
    "review_time" VARCHAR(255),
    "update_time" VARCHAR(255),
    "product_id" VARCHAR(64) NOT NULL REFERENCES "productdbmodel" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "projectdbmodel" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "info" TEXT,
    "repo_type" VARCHAR(64),
    "href" TEXT,
    "icon" TEXT,
    "favor" BOOL NOT NULL,
    "audit_status" VARCHAR(64),
    "publish_time" VARCHAR(255),
    "update_time" VARCHAR(255),
    "publisher_id" VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS "resumedbmodel" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "userid" VARCHAR(255) UNIQUE,
    "introduction" JSONB,
    "updated_at" VARCHAR(64)
);
CREATE TABLE IF NOT EXISTS "userdbmodel" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "userid" VARCHAR(255) NOT NULL UNIQUE,
    "name" VARCHAR(255),
    "pwd" VARCHAR(255) NOT NULL,
    "avatar" TEXT,
    "email" VARCHAR(255),
    "phone" VARCHAR(64),
    "gender" VARCHAR(32),
    "invite_code" VARCHAR(255),
    "role" VARCHAR(255),
    "apply_time" VARCHAR(255),
    "last_login" VARCHAR(255)
);
