import { Controller, Logger, Post, Req, Res } from '@nestjs/common';
import { Request, Response } from 'express';

const AGENT_BASE_URL =
  process.env.AGENT_CHAT_URL ?? 'http://localhost:8000/api/agent/chat';
const AGENT_CHAT_URL = AGENT_BASE_URL;
const AGENT_FEEDBACK_URL = AGENT_BASE_URL.replace(/\/chat$/, '/feedback');

@Controller('agent')
export class AgentChatController {
  private readonly logger = new Logger(AgentChatController.name);

  @Post('chat')
  public async proxyChat(
    @Req() req: Request,
    @Res() res: Response
  ): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };

    const authHeader = req.headers['authorization'];
    if (authHeader) {
      headers['Authorization'] = authHeader as string;
    }

    try {
      const agentResponse = await fetch(AGENT_CHAT_URL, {
        body: JSON.stringify(req.body),
        headers,
        method: 'POST',
        signal: AbortSignal.timeout(60_000)
      });

      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.setHeader('X-Accel-Buffering', 'no');
      res.status(agentResponse.status);

      if (!agentResponse.body) {
        res.end();
        return;
      }

      const reader = agentResponse.body.getReader();

      const pump = async (): Promise<void> => {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            res.end();
            return;
          }

          res.write(value);
          (res as any).flush?.();
        }
      };

      req.on('close', () => {
        reader.cancel().catch(() => {});
      });

      await pump();
    } catch (error) {
      this.logger.error(
        `Agent proxy failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );

      if (!res.headersSent) {
        res.setHeader('Content-Type', 'text/event-stream');
        res.setHeader('Cache-Control', 'no-cache');
        res.status(200);
      }

      res.write(
        `event: error\ndata: ${JSON.stringify({
          code: 'API_ERROR',
          message:
            'Unable to reach the agent service. Please try again shortly.'
        })}\n\n`
      );

      res.end();
    }
  }

  @Post('feedback')
  public async proxyFeedback(
    @Req() req: Request,
    @Res() res: Response
  ): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };

    const authHeader = req.headers['authorization'];
    if (authHeader) {
      headers['Authorization'] = authHeader as string;
    }

    try {
      const agentResponse = await fetch(AGENT_FEEDBACK_URL, {
        body: JSON.stringify(req.body),
        headers,
        method: 'POST',
        signal: AbortSignal.timeout(10_000)
      });

      const data = await agentResponse.json();
      res.status(agentResponse.status).json(data);
    } catch (error) {
      this.logger.error(
        `Agent feedback proxy failed: ${error instanceof Error ? error.message : 'Unknown error'}`
      );

      res.status(502).json({
        message: 'Unable to reach the agent service for feedback.',
        status: 'error'
      });
    }
  }
}
