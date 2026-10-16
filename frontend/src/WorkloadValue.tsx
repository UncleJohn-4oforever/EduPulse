import {rate} from './api';

export const WEEKLY_LESSON_BASE = 15;

export function WorkloadValue({lessons}:{lessons:number}) {
 return <div className="workload-value"><strong>{lessons}/{WEEKLY_LESSON_BASE}</strong><span>{rate(lessons/WEEKLY_LESSON_BASE)}</span></div>;
}
