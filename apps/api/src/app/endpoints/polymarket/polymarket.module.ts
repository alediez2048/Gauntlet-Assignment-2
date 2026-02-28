import { PrismaModule } from '@ghostfolio/api/services/prisma/prisma.module';

import { Module } from '@nestjs/common';

import { PolymarketController } from './polymarket.controller';
import { PolymarketService } from './polymarket.service';

@Module({
  controllers: [PolymarketController],
  imports: [PrismaModule],
  providers: [PolymarketService]
})
export class PolymarketModule {}
