import 'zone.js'; // Required for Angular

import { bootstrapApplication } from '@angular/platform-browser';
import { TravelPlannerComponent } from './app/travel-planner/travel-planner.component';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { routes } from './app/app.routes';
import { provideMarkdown } from 'ngx-markdown';

bootstrapApplication(TravelPlannerComponent, {
  providers: [
    provideAnimations(),
    provideHttpClient(),
    provideRouter(routes),
    provideMarkdown()
  ]
})
  .catch(err => console.error(err));