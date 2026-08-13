-- Migration 001: core schema for Furniture Data Hub
-- CRITICAL: pgvector extension must exist BEFORE tables with VECTOR columns
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$ BEGIN
    CREATE TYPE factory_status AS ENUM ('pending', 'syncing', 'active', 'error');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS factories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    status factory_status NOT NULL DEFAULT 'pending',
    dropbox_url TEXT,
    total_items INT NOT NULL DEFAULT 0,
    last_synced TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    factory_id UUID NOT NULL REFERENCES factories(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    designer_name VARCHAR(255),
    release_year INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    dimensions_raw VARCHAR(255),
    base_price DECIMAL(12,2),
    variations_metadata JSONB DEFAULT '{}'::jsonb,
    review_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    source_file TEXT,
    source_page INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS product_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    text_embedding VECTOR(512),
    image_embedding VECTOR(512)
);

CREATE TABLE IF NOT EXISTS ingest_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    factory_id UUID REFERENCES factories(id) ON DELETE SET NULL,
    celery_task_id VARCHAR(64),
    source VARCHAR(20) NOT NULL DEFAULT 'dropbox',
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    progress INT NOT NULL DEFAULT 0,
    message TEXT,
    files JSONB DEFAULT '[]'::jsonb,
    stats JSONB DEFAULT '{}'::jsonb,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_collection ON products(collection_id);
CREATE INDEX IF NOT EXISTS idx_products_review ON products(review_status);
CREATE INDEX IF NOT EXISTS idx_products_model_trgm ON products USING gin (model_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_collections_factory ON collections(factory_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_product ON product_embeddings(product_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_text_hnsw ON product_embeddings USING hnsw (text_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_embeddings_image_hnsw ON product_embeddings USING hnsw (image_embedding vector_cosine_ops);
