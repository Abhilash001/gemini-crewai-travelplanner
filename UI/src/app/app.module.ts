import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MarkdownModule } from 'ngx-markdown';
import { TravelPlannerComponent } from './travel-planner/travel-planner.component';

@NgModule({
  declarations: [TravelPlannerComponent],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
    ReactiveFormsModule,
    MarkdownModule.forRoot()
  ],
  providers: [],
  bootstrap: [TravelPlannerComponent]
})
export class AppModule {}