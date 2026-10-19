// /pyzed/es/llms-full.txt: toda la documentación en español en un solo archivo Markdown.
import { llmsFull, textResponse } from '../../lib/llms';

export const GET = async () => textResponse(await llmsFull('es'));
