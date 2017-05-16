
-- sac == "steap and cheap"
drop database if exists sac;
create database sac;
use sac;

-- only the scraping process writes to this table
drop table if exists deals;
create table deals (
	id int primary key auto_increment,
	created timestamp default now(),
    product_name varchar(255) unique,
    product_description varchar(4095)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

-- only the UI writes to these two tables
drop table if exists alerts;
create table alerts (
	id int primary key auto_increment,
    user_id int,
    alert_name varchar(127),
    search_terms varchar(1024),
    created timestamp default now(),
    active int default 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

drop table if exists users;
create table users (
	id int primary key auto_increment,
    phone_number varchar(55),
    username varchar(255) unique,
    password varchar(514)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
alter table users add unique (phone_number, username);

-- only the alerting process writes to this table
drop table if exists sent_alerts;
create table sent_alerts (
	id int primary key auto_increment,
	deal_id int,
    alert_id int,
    sent timestamp,
    foreign key (alert_id) references alerts(id),
    foreign key (deal_id) references deals(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

-- the UI reads from this table (all writes to it are manual for now)
-- this is to make new account creation invitation-only :-)
drop table if exists new_account_keys;
create table new_account_keys (
	id int primary key auto_increment,
	new_account_key varchar(127) unique,
    active int default 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

-- turns out we need to have duplicate deals, because they re-run them sometimes
alter table deals drop index product_name;

-- let's store some more info about these deals while we're at it
alter table deals add sale_price decimal(6,2);
alter table deals add brand_name varchar(64);
alter table deals add url varchar(128);

-- adding account text message based activation, removing new account keys stuff
alter table users add active int default 0;
drop table if exists account_activation_keys;
create table account_activation_keys
(
	id int primary key auto_increment,
    phone_number varchar(55),
    activation_key varchar(128),
    received int default 0,
    created timestamp default now()

) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
drop table if exists new_account_keys;
