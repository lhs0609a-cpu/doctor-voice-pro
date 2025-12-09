-- Migration: Add new features (tags, favorites, scheduled posts)
-- Date: 2025-10-30

-- Add new columns to posts table
ALTER TABLE posts ADD COLUMN is_favorited BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE posts ADD COLUMN scheduled_at DATETIME;

-- Update post status enum to include 'scheduled'
-- Note: For SQLite, we need to handle this differently
-- For production with PostgreSQL, use: ALTER TYPE poststatus ADD VALUE 'scheduled';

-- Create tags table
CREATE TABLE IF NOT EXISTS tags (
    id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(20) DEFAULT '#3B82F6' NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create post_tags association table
CREATE TABLE IF NOT EXISTS post_tags (
    post_id CHAR(36) NOT NULL,
    tag_id CHAR(36) NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_posts_is_favorited ON posts(is_favorited);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_at ON posts(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_tags_user_id ON tags(user_id);
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_post_tags_post_id ON post_tags(post_id);
CREATE INDEX IF NOT EXISTS idx_post_tags_tag_id ON post_tags(tag_id);
