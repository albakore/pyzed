// /pyzed/es/llms.txt: el mapa de la documentación en español para asistentes de IA.
import { llmsTxt, textResponse } from '../../lib/llms';

export const GET = async () => textResponse(await llmsTxt('es'));
