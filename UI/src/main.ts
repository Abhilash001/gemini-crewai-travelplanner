import 'zone.js'; // 👈 Required for Angular change detection

import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { importProvidersFrom } from '@angular/core';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';

import { TravelPlannerComponent } from './app/travel-planner/travel-planner.component';

bootstrapApplication(TravelPlannerComponent, {
  providers: [
    provideRouter([
      { path: '', component: TravelPlannerComponent },
      { path: '**', redirectTo: '' }
    ]),
    provideHttpClient(),
    importProvidersFrom(FormsModule, ReactiveFormsModule)
  ]
}).catch(err => console.error(err));