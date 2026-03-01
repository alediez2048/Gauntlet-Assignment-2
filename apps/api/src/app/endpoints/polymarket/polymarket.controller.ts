import { HasPermission } from '@ghostfolio/api/decorators/has-permission.decorator';
import { HasPermissionGuard } from '@ghostfolio/api/guards/has-permission.guard';
import { permissions } from '@ghostfolio/common/permissions';
import type { RequestWithUser } from '@ghostfolio/common/types';

import {
  Body,
  Controller,
  Delete,
  Get,
  HttpException,
  Inject,
  Logger,
  Param,
  Post,
  Query,
  UseGuards
} from '@nestjs/common';
import { REQUEST } from '@nestjs/core';
import { AuthGuard } from '@nestjs/passport';
import { StatusCodes } from 'http-status-codes';

import { PolymarketService } from './polymarket.service';

@Controller('polymarket')
export class PolymarketController {
  private readonly logger = new Logger(PolymarketController.name);

  public constructor(
    private readonly polymarketService: PolymarketService,
    @Inject(REQUEST) private readonly request: RequestWithUser
  ) {}

  @Get('markets')
  public async getMarkets(
    @Query('active') active?: string,
    @Query('category') category?: string,
    @Query('limit') limit?: string,
    @Query('query') query?: string
  ) {
    try {
      return await this.polymarketService.getMarkets({
        active: active !== undefined ? active === 'true' : undefined,
        category: category || undefined,
        limit: limit ? parseInt(limit, 10) : 20,
        query: query || undefined
      });
    } catch (error) {
      this.logger.error(
        `Failed to fetch markets: ${error instanceof Error ? error.message : 'Unknown'}`
      );

      throw new HttpException(
        'Failed to fetch prediction markets',
        StatusCodes.BAD_GATEWAY
      );
    }
  }

  @Get('markets/:slug')
  public async getMarketBySlug(@Param('slug') slug: string) {
    try {
      const market = await this.polymarketService.getMarketBySlug(slug);
      if (!market) {
        throw new HttpException('Market not found', StatusCodes.NOT_FOUND);
      }
      return market;
    } catch (error) {
      if (error instanceof HttpException) {
        throw error;
      }
      this.logger.error(
        `Failed to fetch market ${slug}: ${error instanceof Error ? error.message : 'Unknown'}`
      );

      throw new HttpException(
        'Failed to fetch market details',
        StatusCodes.BAD_GATEWAY
      );
    }
  }

  @HasPermission(permissions.createOrder)
  @Post('positions')
  @UseGuards(AuthGuard('jwt'), HasPermissionGuard)
  public async createPosition(
    @Body()
    body: {
      slug: string;
      question: string;
      outcome: string;
      outcomePrice: number;
      quantity: number;
    }
  ) {
    try {
      return await this.polymarketService.createPosition(
        this.request.user.id,
        body
      );
    } catch (error) {
      this.logger.error(
        `Failed to create position: ${error instanceof Error ? error.message : 'Unknown'}`
      );

      throw new HttpException(
        'Failed to create position',
        StatusCodes.INTERNAL_SERVER_ERROR
      );
    }
  }

  @Get('positions')
  @UseGuards(AuthGuard('jwt'))
  public async getPositions() {
    try {
      return await this.polymarketService.getPositions(this.request.user.id);
    } catch (error) {
      this.logger.error(
        `Failed to fetch positions: ${error instanceof Error ? error.message : 'Unknown'}`
      );

      throw new HttpException(
        'Failed to fetch positions',
        StatusCodes.INTERNAL_SERVER_ERROR
      );
    }
  }

  @HasPermission(permissions.deleteOrder)
  @Delete('positions/:id')
  @UseGuards(AuthGuard('jwt'), HasPermissionGuard)
  public async deletePosition(@Param('id') id: string) {
    const result = await this.polymarketService.deletePosition(
      this.request.user.id,
      id
    );

    if (!result) {
      throw new HttpException('Position not found', StatusCodes.NOT_FOUND);
    }

    return result;
  }
}
