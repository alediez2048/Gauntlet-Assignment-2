import { defineConfig } from '@prisma/config';
import { config } from 'dotenv';
import { expand } from 'dotenv-expand';
import { join } from 'node:path';

// Load .env from project root so Prisma gets DATABASE_URL regardless of cwd
const pathToEnv = join(__dirname, '..', '.env');
expand(config({ path: pathToEnv, quiet: true }));

export default defineConfig({
  migrations: {
    path: join(__dirname, '..', 'prisma', 'migrations'),
    seed: `node ${join(__dirname, '..', 'prisma', 'seed.mts')}`
  },
  schema: join(__dirname, '..', 'prisma', 'schema.prisma')
});
