-- FoodConnect AI / AI Smart Food Donation Platform
-- MySQL 8.0+ (also compatible with MariaDB 10.6+).
-- Run as a database administrator: mysql -u root -p < database/schema.sql
-- Application credentials are configured separately in .env, never in this file.
-- All dates are UTC. Data is inserted via `flask --app app seed`.
CREATE DATABASE IF NOT EXISTS foodconnect CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE foodconnect;

CREATE TABLE IF NOT EXISTS users (
	id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(120) NOT NULL,
	email VARCHAR(180) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	active BOOL NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `admin` (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS charities (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	organization VARCHAR(160) NOT NULL,
	phone VARCHAR(40) NOT NULL,
	location VARCHAR(255) NOT NULL,
	latitude FLOAT NOT NULL,
	longitude FLOAT NOT NULL,
	categories VARCHAR(255) NOT NULL,
	required_quantity FLOAT NOT NULL,
	unit VARCHAR(20) NOT NULL,
	vegetarian_only BOOL NOT NULL,
	max_distance FLOAT NOT NULL,
	description TEXT,
	PRIMARY KEY (id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS donors (
	id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	organization VARCHAR(160) NOT NULL,
	phone VARCHAR(40) NOT NULL,
	location VARCHAR(255) NOT NULL,
	latitude FLOAT NOT NULL,
	longitude FLOAT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (user_id),
	FOREIGN KEY(user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS food_donations (
	id INTEGER NOT NULL AUTO_INCREMENT,
	donor_id INTEGER NOT NULL,
	name VARCHAR(160) NOT NULL,
	category VARCHAR(40) NOT NULL,
	quantity FLOAT NOT NULL,
	unit VARCHAR(20) NOT NULL,
	prepared_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	`condition` VARCHAR(40) NOT NULL,
	vegetarian BOOL NOT NULL,
	location VARCHAR(255) NOT NULL,
	latitude FLOAT NOT NULL,
	longitude FLOAT NOT NULL,
	contact VARCHAR(80) NOT NULL,
	urgency VARCHAR(20) NOT NULL,
	notes TEXT,
	status VARCHAR(20) NOT NULL,
	accepted_charity_id INTEGER,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(donor_id) REFERENCES donors (id),
	FOREIGN KEY(accepted_charity_id) REFERENCES charities (id),
	INDEX ix_food_donations_status (status),
	INDEX ix_food_donations_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS donation_status (
	id INTEGER NOT NULL AUTO_INCREMENT,
	donation_id INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	changed_by INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(donation_id) REFERENCES food_donations (id),
	FOREIGN KEY(changed_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS matches (
	id INTEGER NOT NULL AUTO_INCREMENT,
	donation_id INTEGER NOT NULL,
	charity_id INTEGER NOT NULL,
	score FLOAT NOT NULL,
	distance FLOAT NOT NULL,
	explanation TEXT NOT NULL,
	response VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_donation_charity UNIQUE (donation_id, charity_id),
	FOREIGN KEY(donation_id) REFERENCES food_donations (id),
	FOREIGN KEY(charity_id) REFERENCES charities (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
