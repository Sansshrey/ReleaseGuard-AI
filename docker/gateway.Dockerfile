FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY dotnet/ReleaseGuard.Gateway/bin/Release/net10.0/ ./
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet","ReleaseGuard.Gateway.dll"]