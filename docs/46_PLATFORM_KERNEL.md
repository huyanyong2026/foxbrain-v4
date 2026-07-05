# 46 Platform Kernel

## Goal

Platform Kernel makes FoxBrain feel like one enterprise AI operating system instead of separate pages.

## Core Structures

- System Module
- System Object
- System Event
- System Notification
- System Setting
- User Workspace
- Module Health
- Data Readiness
- AI Context Packet

## Routes

- `/workspace`
- `/boss`
- `/employee-workspace`
- `/settings`
- `/system/modules`
- `/system/data-readiness`
- `/notifications`
- `/risks`
- `/timeline`

## Safety

Kernel APIs expose status and context only. Secrets are never returned.

## Task021 Integration

The kernel now includes SAP sync, data pipeline, data freshness and scheduler health as first-class system status.
