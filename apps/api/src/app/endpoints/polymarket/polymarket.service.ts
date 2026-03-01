import { PrismaService } from '@ghostfolio/api/services/prisma/prisma.service';

import { Injectable, Logger } from '@nestjs/common';
import { DataSource } from '@prisma/client';

const GAMMA_API_BASE = 'https://gamma-api.polymarket.com';

@Injectable()
export class PolymarketService {
  private readonly logger = new Logger(PolymarketService.name);

  public constructor(private readonly prismaService: PrismaService) {}

  public async getMarkets(params: {
    active?: boolean;
    category?: string;
    limit?: number;
    query?: string;
  }): Promise<any[]> {
    const url = new URL(`${GAMMA_API_BASE}/markets`);

    // Default to active markets sorted by 24h volume (most traded first)
    url.searchParams.set('active', String(params.active ?? true));
    url.searchParams.set('closed', 'false');
    url.searchParams.set('order', 'volume24hr');
    url.searchParams.set('ascending', 'false');

    if (params.category) {
      url.searchParams.set('tag', params.category);
    }

    // When searching, fetch more markets so client-side text filtering has a larger pool
    const fetchLimit = params.query ? 100 : (params.limit ?? 20);
    url.searchParams.set('limit', String(fetchLimit));

    const response = await fetch(url.toString(), {
      signal: AbortSignal.timeout(10_000)
    });

    if (!response.ok) {
      this.logger.error(`Gamma API error: ${response.status}`);
      throw new Error(`Gamma API returned ${response.status}`);
    }

    let markets: any[] = await response.json();

    // Client-side text search (Gamma API has no full-text query parameter)
    // Uses progressive word-level matching: try ALL words first, then
    // progressively drop trailing words until results are found.
    // e.g. "jesus return to earth" → try all 3 → no match → try "jesus return" → match!
    if (params.query) {
      const stopWords = new Set([
        'a',
        'an',
        'the',
        'to',
        'of',
        'in',
        'by',
        'for',
        'and',
        'or',
        'is',
        'my',
        'if',
        'i'
      ]);
      const words = params.query
        .toLowerCase()
        .split(/[\s\-]+/)
        .filter((w) => w.length >= 2 && !stopWords.has(w));

      let filtered: any[] = [];
      for (
        let count = words.length;
        count >= 1 && filtered.length === 0;
        count--
      ) {
        const subset = words.slice(0, count);
        filtered = markets.filter((m: any) => {
          const text = [
            m.question || '',
            (m.slug || '').replace(/-/g, ' '),
            m.description || ''
          ]
            .join(' ')
            .toLowerCase();
          return subset.every((w) => text.includes(w));
        });
      }
      markets = filtered.slice(0, params.limit ?? 20);
    }

    return markets;
  }

  public async getMarketBySlug(slug: string): Promise<any> {
    // Gamma API uses ?slug= query param, not /markets/{slug} path
    const url = new URL(`${GAMMA_API_BASE}/markets`);
    url.searchParams.set('slug', slug);

    const response = await fetch(url.toString(), {
      signal: AbortSignal.timeout(10_000)
    });

    if (!response.ok) {
      this.logger.error(`Gamma API error for slug ${slug}: ${response.status}`);
      throw new Error(`Gamma API returned ${response.status}`);
    }

    const data: any[] = await response.json();
    return Array.isArray(data) && data.length > 0 ? data[0] : null;
  }

  public async createPosition(
    userId: string,
    data: {
      slug: string;
      question: string;
      outcome: string;
      outcomePrice: number;
      quantity: number;
    }
  ) {
    const symbolProfile = await this.prismaService.symbolProfile.upsert({
      create: {
        currency: 'USD',
        dataSource: DataSource.POLYMARKET,
        name: data.question,
        symbol: data.slug
      },
      update: {
        name: data.question
      },
      where: {
        dataSource_symbol: {
          dataSource: DataSource.POLYMARKET,
          symbol: data.slug
        }
      }
    });

    const order = await this.prismaService.order.create({
      data: {
        comment: `${data.outcome} @ ${data.outcomePrice}`,
        currency: 'USD',
        date: new Date(),
        fee: 0,
        quantity: data.quantity,
        type: 'BUY',
        unitPrice: data.outcomePrice,
        SymbolProfile: {
          connect: { id: symbolProfile.id }
        },
        user: {
          connect: { id: userId }
        }
      }
    });

    return { order, symbolProfile };
  }

  public async getPositions(userId: string) {
    return this.prismaService.order.findMany({
      where: {
        userId,
        SymbolProfile: {
          dataSource: DataSource.POLYMARKET
        }
      },
      include: {
        SymbolProfile: true
      },
      orderBy: {
        date: 'desc'
      }
    });
  }

  public async deletePosition(userId: string, orderId: string) {
    const order = await this.prismaService.order.findFirst({
      where: {
        id: orderId,
        userId,
        SymbolProfile: {
          dataSource: DataSource.POLYMARKET
        }
      }
    });

    if (!order) {
      return null;
    }

    return this.prismaService.order.delete({
      where: { id: orderId }
    });
  }
}
