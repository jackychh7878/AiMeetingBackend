CREATE EXTENSION IF NOT EXISTS vector;

create table public.ai_meeting_app_owner_control
(
    sys_id        serial
        primary key,
    name          varchar(255)                         not null,
    quota_hours   double precision default 0           not null,
    usage_hours   double precision default 0           not null,
    valid_to      date,
    metadata_json jsonb            default '{}'::jsonb not null,
    created_dt    timestamp        default CURRENT_TIMESTAMP,
    remarks       text
);
INSERT INTO public.ai_meeting_app_owner_control
    (sys_id, name, quota_hours, usage_hours, valid_to, metadata_json, created_dt, remarks)
values (DEFAULT, 'catomind', 100, 0, '2027-01-01', DEFAULT, DEFAULT, 'DEV');


create table public.voiceprint_library
(
    sys_id        serial
        primary key,
    name          varchar(255)                  not null,
    email         varchar(255),
    department    varchar(255),
    position      varchar(255),
    embedding     vector(256),
    metadata_json jsonb     default '{}'::jsonb not null,
    created_dt    timestamp default CURRENT_TIMESTAMP
); 