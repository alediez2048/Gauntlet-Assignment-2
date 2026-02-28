# Skill: Database Migration Manager

Safely manage Prisma schema changes, migrations, and seeding.

## When to Use

User says: "migrate database", "update schema", "add column", "db migrate", "prisma migrate", "reset database"

## Workflow

### Step 1: Understand the Change

Read the current schema:

```bash
cat prisma/schema.prisma
```

Identify what's changing: new model, new field, field type change, relation change, etc.

### Step 2: Make Schema Changes

Edit `prisma/schema.prisma` as needed.

**Validate the schema:**

```bash
npx prisma validate
```

**Format the schema:**

```bash
npx prisma format
```

### Step 3: Create Migration

**For development (creates migration + applies it):**

```bash
npx prisma migrate dev --name <descriptive-name>
```

Naming convention: `add_field_name`, `create_table_name`, `remove_column_name`

**For prototype/quick sync (no migration file, direct push):**

```bash
npx prisma db push
```

WARNING: `db push` does NOT create a migration file. Use only for rapid prototyping.

### Step 4: Regenerate Prisma Client

```bash
npx prisma generate
```

This updates the TypeScript types used by the NestJS API.

### Step 5: Verify

**Open Prisma Studio to inspect data:**

```bash
npm run database:gui
```

**Run API tests to check nothing broke:**

```bash
npx nx test api
```

### Step 6: Deploy Migration

**Local (already applied by `migrate dev`).**

**Railway production:**

The Dockerfile entrypoint runs `npx prisma migrate deploy` automatically on startup. Just redeploy the ghostfolio service.

## Commands Reference

| Command                           | Purpose                                  | When to Use              |
| --------------------------------- | ---------------------------------------- | ------------------------ |
| `npx prisma validate`             | Check schema syntax                      | Before any migration     |
| `npx prisma format`               | Auto-format schema                       | After editing schema     |
| `npx prisma migrate dev --name X` | Create + apply migration                 | Development              |
| `npx prisma db push`              | Quick sync (no migration file)           | Prototyping only         |
| `npx prisma migrate deploy`       | Apply pending migrations                 | Production deploy        |
| `npx prisma migrate reset`        | Drop DB + re-apply all migrations + seed | Full reset (destructive) |
| `npx prisma generate`             | Regenerate TypeScript client             | After schema changes     |
| `npx prisma studio`               | Visual DB browser                        | Inspection/debugging     |
| `npx prisma db seed`              | Run seed script                          | After reset or fresh DB  |

## Key Files

| File                    | Purpose                      |
| ----------------------- | ---------------------------- |
| `prisma/schema.prisma`  | Database schema (48+ models) |
| `prisma/migrations/`    | Migration history            |
| `prisma/seed.mts`       | Seed script                  |
| `docker/seed-data.json` | Seed transaction data        |

## Safety Rules

1. **NEVER** run `migrate reset` on production
2. **ALWAYS** validate schema before creating migration
3. **ALWAYS** check migration SQL before applying: `npx prisma migrate diff --from-schema-datamodel prisma/schema.prisma --to-schema-datasource prisma/schema.prisma`
4. **ALWAYS** test with `npx nx test api` after migration
5. Back up production data before deploying breaking schema changes
