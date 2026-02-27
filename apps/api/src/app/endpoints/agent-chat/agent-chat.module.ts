import { Module } from '@nestjs/common';

import { AgentChatController } from './agent-chat.controller';

@Module({
  controllers: [AgentChatController]
})
export class AgentChatModule {}
